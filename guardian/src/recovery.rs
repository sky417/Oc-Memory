use anyhow::Result;
use chrono::Utc;
use regex::Regex;
use std::collections::HashMap;
use std::path::Path;
use std::time::{Duration, Instant};
use tracing::{error, info, warn};

use crate::config::{RecoveryConfig, RecoveryScenario};
use crate::health::{BackupManager, HealthCheckResult, HealthStatus};
use crate::process::ProcessManager;

// =============================================================================
// Recovery Action
// =============================================================================

#[derive(Debug, Clone, PartialEq)]
pub enum RecoveryAction {
    RestoreBackup { path: String },
    Restart,
    RestartWithDependencies,
    GracefulRestart { grace_period: u64 },
    ExponentialBackoff { max_backoff: u64 },
    LogWarning,
    Notify { message: String },
    GiveUp,
}

impl std::fmt::Display for RecoveryAction {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RecoveryAction::RestoreBackup { path } => write!(f, "restore_backup({})", path),
            RecoveryAction::Restart => write!(f, "restart"),
            RecoveryAction::RestartWithDependencies => write!(f, "restart_with_deps"),
            RecoveryAction::GracefulRestart { grace_period } => {
                write!(f, "graceful_restart({}s)", grace_period)
            }
            RecoveryAction::ExponentialBackoff { max_backoff } => {
                write!(f, "exponential_backoff(max={}s)", max_backoff)
            }
            RecoveryAction::LogWarning => write!(f, "log_warning"),
            RecoveryAction::Notify { .. } => write!(f, "notify"),
            RecoveryAction::GiveUp => write!(f, "give_up"),
        }
    }
}

// =============================================================================
// Recovery Event Log (Sprint 2.5.4: statistics)
// =============================================================================

#[derive(Debug, Clone, serde::Serialize)]
pub struct RecoveryEvent {
    pub timestamp: String,
    pub process_name: String,
    pub scenario: String,
    pub action: String,
    pub success: bool,
    pub details: String,
}

// =============================================================================
// Recovery Stats
// =============================================================================

#[derive(Debug, Default)]
pub struct RecoveryStats {
    pub total_recoveries: u64,
    pub successful: u64,
    pub failed: u64,
    pub by_scenario: HashMap<String, u64>,
    pub events: Vec<RecoveryEvent>,
}

impl RecoveryStats {
    /// Log a recovery event in JSON format
    fn record_event(
        &mut self,
        process_name: &str,
        scenario: &str,
        action: &str,
        success: bool,
        details: &str,
    ) {
        let event = RecoveryEvent {
            timestamp: Utc::now().to_rfc3339(),
            process_name: process_name.to_string(),
            scenario: scenario.to_string(),
            action: action.to_string(),
            success,
            details: details.to_string(),
        };

        if let Ok(json) = serde_json::to_string(&event) {
            info!(target: "recovery_stats", "{}", json);
        }

        // Keep last 100 events in memory
        if self.events.len() >= 100 {
            self.events.remove(0);
        }
        self.events.push(event);
    }
}

// =============================================================================
// Recovery Engine
// =============================================================================

pub struct RecoveryEngine {
    config: RecoveryConfig,
    stats: RecoveryStats,
    backoff_state: HashMap<String, BackoffState>,
}

#[derive(Debug)]
struct BackoffState {
    current_delay: u64,
    last_attempt: Instant,
    attempt_count: u32,
}

impl RecoveryEngine {
    pub fn new(config: RecoveryConfig) -> Self {
        Self {
            config,
            stats: RecoveryStats::default(),
            backoff_state: HashMap::new(),
        }
    }

    /// Evaluate health check results and determine recovery action
    pub fn evaluate(
        &mut self,
        process_name: &str,
        health_result: &HealthCheckResult,
        restart_count: u32,
    ) -> Option<RecoveryAction> {
        match &health_result.status {
            HealthStatus::Healthy => {
                // Reset backoff on healthy
                self.backoff_state.remove(process_name);
                None
            }
            HealthStatus::Unknown => None,
            HealthStatus::Degraded(msg) | HealthStatus::Unhealthy(msg) => {
                // Check if we've exceeded max restarts
                if restart_count >= self.config.max_restarts {
                    warn!(
                        "Process '{}' exceeded max restarts ({}), giving up",
                        process_name, self.config.max_restarts
                    );
                    return Some(self.get_give_up_action(process_name, msg));
                }

                // Match against scenarios
                self.match_scenario(process_name, health_result, msg)
            }
        }
    }

    /// Match health check failure against configured scenarios
    fn match_scenario(
        &mut self,
        process_name: &str,
        health_result: &HealthCheckResult,
        failure_msg: &str,
    ) -> Option<RecoveryAction> {
        let scenarios = self.config.scenarios.clone();

        for scenario in &scenarios {
            if Self::trigger_matches(scenario, health_result, failure_msg) {
                info!(
                    "Recovery scenario '{}' matched for process '{}'",
                    scenario.name, process_name
                );

                self.stats.total_recoveries += 1;
                *self
                    .stats
                    .by_scenario
                    .entry(scenario.name.clone())
                    .or_insert(0) += 1;

                return Some(self.scenario_to_action(process_name, scenario));
            }
        }

        // Default: restart
        info!(
            "No specific scenario matched for '{}', defaulting to restart",
            process_name
        );
        self.stats.total_recoveries += 1;
        *self
            .stats
            .by_scenario
            .entry("default_restart".to_string())
            .or_insert(0) += 1;

        Some(RecoveryAction::Restart)
    }

    /// Check if a trigger condition matches
    fn trigger_matches(
        scenario: &RecoveryScenario,
        health_result: &HealthCheckResult,
        failure_msg: &str,
    ) -> bool {
        let trigger = &scenario.trigger;

        if trigger == "config_validation_failed" {
            return health_result
                .level_results
                .iter()
                .any(|r| r.level == 3 && !r.passed);
        }

        if trigger.starts_with("exit_code") {
            return health_result
                .level_results
                .iter()
                .any(|r| r.level == 1 && !r.passed);
        }

        if trigger == "log_activity_timeout" {
            return health_result
                .level_results
                .iter()
                .any(|r| r.level == 2 && !r.passed && r.message.contains("stale"));
        }

        if trigger.starts_with("memory >") || trigger == "memory > max_memory_mb" {
            return health_result
                .level_results
                .iter()
                .any(|r| r.level == 4 && !r.passed && r.message.contains("Memory"));
        }

        if trigger.starts_with("restart_count >") {
            return false;
        }

        if trigger.starts_with("log_pattern") {
            if let Some(start) = trigger.find('\'') {
                if let Some(end) = trigger.rfind('\'') {
                    if start != end {
                        let pattern = &trigger[start + 1..end];
                        if let Ok(re) = Regex::new(pattern) {
                            return re.is_match(failure_msg);
                        }
                    }
                }
            }
        }

        false
    }

    /// Convert a scenario to a recovery action
    fn scenario_to_action(
        &mut self,
        process_name: &str,
        scenario: &RecoveryScenario,
    ) -> RecoveryAction {
        match scenario.action.as_str() {
            "restore_backup" => {
                if let Some(ref backup_path) = scenario.backup_path {
                    RecoveryAction::RestoreBackup {
                        path: backup_path.clone(),
                    }
                } else {
                    RecoveryAction::Restart
                }
            }
            "restart_with_dependencies" => RecoveryAction::RestartWithDependencies,
            "graceful_restart" => RecoveryAction::GracefulRestart {
                grace_period: scenario.grace_period,
            },
            "exponential_backoff" => {
                let max_backoff = scenario.max_backoff.unwrap_or(self.config.max_backoff);
                self.apply_backoff(process_name, max_backoff);
                RecoveryAction::ExponentialBackoff { max_backoff }
            }
            "log_warning" => RecoveryAction::LogWarning,
            _ => RecoveryAction::Restart,
        }
    }

    /// Apply exponential backoff for a process
    fn apply_backoff(&mut self, process_name: &str, max_backoff: u64) {
        let state = self
            .backoff_state
            .entry(process_name.to_string())
            .or_insert(BackoffState {
                current_delay: self.config.initial_backoff,
                last_attempt: Instant::now(),
                attempt_count: 0,
            });

        state.attempt_count += 1;
        state.current_delay = (state.current_delay * 2).min(max_backoff);
        state.last_attempt = Instant::now();
    }

    /// Get the current backoff delay for a process
    pub fn get_backoff_delay(&self, process_name: &str) -> Duration {
        self.backoff_state
            .get(process_name)
            .map(|s| Duration::from_secs(s.current_delay))
            .unwrap_or(Duration::from_secs(self.config.initial_backoff))
    }

    /// Determine action when max restarts exceeded
    fn get_give_up_action(&self, process_name: &str, msg: &str) -> RecoveryAction {
        match self.config.give_up_action.as_str() {
            "notify" => RecoveryAction::Notify {
                message: format!(
                    "Process '{}' exceeded max restarts. Last error: {}",
                    process_name, msg
                ),
            },
            "shutdown_all" => RecoveryAction::GiveUp,
            "keep_trying" => RecoveryAction::Restart,
            _ => RecoveryAction::Notify {
                message: format!("Process '{}' recovery failed", process_name),
            },
        }
    }

    /// Execute a recovery action (Sprint 2.5: with stats logging)
    pub async fn execute(
        &mut self,
        action: &RecoveryAction,
        process_name: &str,
        process_manager: &ProcessManager,
    ) -> Result<()> {
        let action_str = action.to_string();
        let scenario_name = self.find_scenario_name(action);

        let result = self
            .execute_inner(action, process_name, process_manager)
            .await;

        // Record event
        match &result {
            Ok(()) => {
                self.stats.record_event(
                    process_name,
                    &scenario_name,
                    &action_str,
                    true,
                    "Recovery action completed",
                );
            }
            Err(e) => {
                self.stats.record_event(
                    process_name,
                    &scenario_name,
                    &action_str,
                    false,
                    &format!("Recovery failed: {}", e),
                );
            }
        }

        result
    }

    fn find_scenario_name(&self, action: &RecoveryAction) -> String {
        match action {
            RecoveryAction::RestoreBackup { .. } => "invalid_json".to_string(),
            RecoveryAction::RestartWithDependencies => "process_crash".to_string(),
            RecoveryAction::GracefulRestart { .. } => "unresponsive".to_string(),
            RecoveryAction::ExponentialBackoff { .. } => "network_timeout".to_string(),
            RecoveryAction::LogWarning => "llm_error".to_string(),
            RecoveryAction::Notify { .. } => "give_up".to_string(),
            RecoveryAction::GiveUp => "give_up".to_string(),
            RecoveryAction::Restart => "default_restart".to_string(),
        }
    }

    async fn execute_inner(
        &mut self,
        action: &RecoveryAction,
        process_name: &str,
        process_manager: &ProcessManager,
    ) -> Result<()> {
        match action {
            RecoveryAction::RestoreBackup { path } => {
                info!(
                    "Restoring backup for '{}' from '{}'",
                    process_name, path
                );

                let proc_arc = process_manager.processes.get(process_name);
                if let Some(proc_arc) = proc_arc {
                    let proc = proc_arc.lock().await;
                    if let Some(ref config_file) = proc.config.health.config_file {
                        // Try generational backup first, fall back to specified path
                        if BackupManager::restore_latest(config_file).is_err() {
                            if Path::new(path).exists() {
                                std::fs::copy(path, config_file)?;
                                info!("Fallback backup restored: {} -> {}", path, config_file);
                            } else {
                                warn!("No backup available: {}", path);
                            }
                        }
                    }
                }

                process_manager.restart_process(process_name).await?;
                self.stats.successful += 1;
            }

            RecoveryAction::Restart => {
                info!("Restarting process '{}'", process_name);
                process_manager.restart_process(process_name).await?;
                self.stats.successful += 1;
            }

            RecoveryAction::RestartWithDependencies => {
                info!(
                    "Restarting process '{}' with dependencies",
                    process_name
                );
                process_manager.stop_all().await?;
                process_manager.start_all().await?;
                self.stats.successful += 1;
            }

            RecoveryAction::GracefulRestart { grace_period } => {
                info!(
                    "Graceful restart for '{}' (grace: {}s)",
                    process_name, grace_period
                );
                process_manager.stop_process(process_name).await?;
                tokio::time::sleep(Duration::from_secs(*grace_period)).await;
                process_manager.start_process(process_name).await?;
                self.stats.successful += 1;
            }

            RecoveryAction::ExponentialBackoff { max_backoff: _ } => {
                let delay = self.get_backoff_delay(process_name);
                info!(
                    "Exponential backoff for '{}': waiting {:?}",
                    process_name, delay
                );
                tokio::time::sleep(delay).await;
                process_manager.restart_process(process_name).await?;
                self.stats.successful += 1;
            }

            RecoveryAction::LogWarning => {
                warn!("Recovery: log warning only for '{}'", process_name);
            }

            RecoveryAction::Notify { message } => {
                error!("Recovery notification: {}", message);
                self.stats.failed += 1;
            }

            RecoveryAction::GiveUp => {
                error!("Giving up on process '{}'", process_name);
                self.stats.failed += 1;
            }
        }

        Ok(())
    }

    /// Get recovery statistics
    pub fn stats(&self) -> &RecoveryStats {
        &self.stats
    }
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health::LevelResult;

    fn default_config() -> RecoveryConfig {
        RecoveryConfig {
            max_restarts: 5,
            restart_window: 300,
            backoff_strategy: "exponential".to_string(),
            initial_backoff: 1,
            max_backoff: 60,
            give_up_action: "notify".to_string(),
            scenarios: vec![
                RecoveryScenario {
                    name: "invalid_json".to_string(),
                    trigger: "config_validation_failed".to_string(),
                    action: "restore_backup".to_string(),
                    backup_path: Some("/tmp/backup.json".to_string()),
                    then: Some("restart".to_string()),
                    cascade: false,
                    grace_period: 30,
                    max_backoff: None,
                    notify: true,
                },
                RecoveryScenario {
                    name: "process_crash".to_string(),
                    trigger: "exit_code != 0".to_string(),
                    action: "restart_with_dependencies".to_string(),
                    backup_path: None,
                    then: None,
                    cascade: true,
                    grace_period: 30,
                    max_backoff: None,
                    notify: true,
                },
                RecoveryScenario {
                    name: "unresponsive".to_string(),
                    trigger: "log_activity_timeout".to_string(),
                    action: "graceful_restart".to_string(),
                    backup_path: None,
                    then: None,
                    cascade: false,
                    grace_period: 30,
                    max_backoff: None,
                    notify: true,
                },
                RecoveryScenario {
                    name: "memory_leak".to_string(),
                    trigger: "memory > max_memory_mb".to_string(),
                    action: "graceful_restart".to_string(),
                    backup_path: None,
                    then: None,
                    cascade: true,
                    grace_period: 30,
                    max_backoff: None,
                    notify: true,
                },
                RecoveryScenario {
                    name: "llm_error".to_string(),
                    trigger: "log_pattern = 'LLM.*error|API.*failed'".to_string(),
                    action: "log_warning".to_string(),
                    backup_path: None,
                    then: None,
                    cascade: false,
                    grace_period: 30,
                    max_backoff: None,
                    notify: false,
                },
            ],
        }
    }

    #[test]
    fn test_healthy_returns_none() {
        let mut engine = RecoveryEngine::new(default_config());

        let result = HealthCheckResult {
            process_name: "test".to_string(),
            status: HealthStatus::Healthy,
            level_results: vec![],
            checked_at: Instant::now(),
        };

        assert!(engine.evaluate("test", &result, 0).is_none());
    }

    #[test]
    fn test_max_restarts_gives_up() {
        let mut engine = RecoveryEngine::new(default_config());

        let result = HealthCheckResult {
            process_name: "test".to_string(),
            status: HealthStatus::Unhealthy("Process dead".to_string()),
            level_results: vec![],
            checked_at: Instant::now(),
        };

        let action = engine.evaluate("test", &result, 5);
        match action {
            Some(RecoveryAction::Notify { .. }) => {}
            other => panic!("Expected Notify, got {:?}", other),
        }
    }

    #[test]
    fn test_process_crash_scenario() {
        let mut engine = RecoveryEngine::new(default_config());

        let result = HealthCheckResult {
            process_name: "test".to_string(),
            status: HealthStatus::Unhealthy("PID not found".to_string()),
            level_results: vec![LevelResult {
                level: 1,
                name: "Process Alive".to_string(),
                passed: false,
                message: "PID not found".to_string(),
            }],
            checked_at: Instant::now(),
        };

        let action = engine.evaluate("test", &result, 0);
        assert_eq!(action, Some(RecoveryAction::RestartWithDependencies));
    }

    #[test]
    fn test_config_validation_scenario() {
        let mut engine = RecoveryEngine::new(default_config());

        let result = HealthCheckResult {
            process_name: "test".to_string(),
            status: HealthStatus::Unhealthy("Invalid JSON".to_string()),
            level_results: vec![LevelResult {
                level: 3,
                name: "Config Validation".to_string(),
                passed: false,
                message: "Invalid JSON: unexpected token".to_string(),
            }],
            checked_at: Instant::now(),
        };

        let action = engine.evaluate("test", &result, 0);
        match action {
            Some(RecoveryAction::RestoreBackup { .. }) => {}
            other => panic!("Expected RestoreBackup, got {:?}", other),
        }
    }

    #[test]
    fn test_log_stale_scenario() {
        let mut engine = RecoveryEngine::new(default_config());

        let result = HealthCheckResult {
            process_name: "test".to_string(),
            status: HealthStatus::Degraded("Log stale".to_string()),
            level_results: vec![LevelResult {
                level: 2,
                name: "Log Activity".to_string(),
                passed: false,
                message: "Log stale: last updated 600s ago (timeout: 300s)".to_string(),
            }],
            checked_at: Instant::now(),
        };

        let action = engine.evaluate("test", &result, 0);
        match action {
            Some(RecoveryAction::GracefulRestart { grace_period: 30 }) => {}
            other => panic!("Expected GracefulRestart(30), got {:?}", other),
        }
    }

    #[test]
    fn test_memory_leak_scenario() {
        let mut engine = RecoveryEngine::new(default_config());

        let result = HealthCheckResult {
            process_name: "test".to_string(),
            status: HealthStatus::Unhealthy("Memory high".to_string()),
            level_results: vec![LevelResult {
                level: 4,
                name: "Resource Usage".to_string(),
                passed: false,
                message: "Memory: 3000MB/2048MB, CPU: 50.0%/90.0%".to_string(),
            }],
            checked_at: Instant::now(),
        };

        let action = engine.evaluate("test", &result, 0);
        match action {
            Some(RecoveryAction::GracefulRestart { .. }) => {}
            other => panic!("Expected GracefulRestart, got {:?}", other),
        }
    }

    #[test]
    fn test_backoff_increases() {
        let mut engine = RecoveryEngine::new(default_config());

        engine.apply_backoff("test", 60);
        let delay1 = engine.get_backoff_delay("test");

        engine.apply_backoff("test", 60);
        let delay2 = engine.get_backoff_delay("test");

        assert!(delay2 > delay1);
    }

    #[test]
    fn test_backoff_caps_at_max() {
        let mut engine = RecoveryEngine::new(default_config());

        for _ in 0..20 {
            engine.apply_backoff("test", 60);
        }

        let delay = engine.get_backoff_delay("test");
        assert!(delay <= Duration::from_secs(60));
    }

    #[test]
    fn test_recovery_stats_tracking() {
        let mut engine = RecoveryEngine::new(default_config());

        let result = HealthCheckResult {
            process_name: "test".to_string(),
            status: HealthStatus::Unhealthy("PID not found".to_string()),
            level_results: vec![LevelResult {
                level: 1,
                name: "Process Alive".to_string(),
                passed: false,
                message: "PID not found".to_string(),
            }],
            checked_at: Instant::now(),
        };

        engine.evaluate("test", &result, 0);
        engine.evaluate("test", &result, 1);

        assert_eq!(engine.stats().total_recoveries, 2);
        assert_eq!(engine.stats().by_scenario["process_crash"], 2);
    }

    #[test]
    fn test_recovery_action_display() {
        assert_eq!(RecoveryAction::Restart.to_string(), "restart");
        assert_eq!(
            RecoveryAction::GracefulRestart { grace_period: 30 }.to_string(),
            "graceful_restart(30s)"
        );
        assert_eq!(
            RecoveryAction::ExponentialBackoff { max_backoff: 60 }.to_string(),
            "exponential_backoff(max=60s)"
        );
    }

    #[test]
    fn test_give_up_shutdown_all() {
        let mut config = default_config();
        config.give_up_action = "shutdown_all".to_string();
        let engine = RecoveryEngine::new(config);

        let action = engine.get_give_up_action("test", "fatal");
        assert_eq!(action, RecoveryAction::GiveUp);
    }

    #[test]
    fn test_give_up_keep_trying() {
        let mut config = default_config();
        config.give_up_action = "keep_trying".to_string();
        let engine = RecoveryEngine::new(config);

        let action = engine.get_give_up_action("test", "fatal");
        assert_eq!(action, RecoveryAction::Restart);
    }
}
