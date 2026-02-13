use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use regex::Regex;
use std::collections::HashMap;
use std::path::Path;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::process::{Child, Command};
use tokio::sync::Mutex;
use tracing::{error, info, warn};

use crate::config::{GuardianConfig, ProcessConfig, ReadyMethod};

// =============================================================================
// Process State
// =============================================================================

#[derive(Debug, Clone, PartialEq)]
pub enum ProcessState {
    Stopped,
    Starting,
    Running,
    Stopping,
    Failed,
}

impl std::fmt::Display for ProcessState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProcessState::Stopped => write!(f, "stopped"),
            ProcessState::Starting => write!(f, "starting"),
            ProcessState::Running => write!(f, "online"),
            ProcessState::Stopping => write!(f, "stopping"),
            ProcessState::Failed => write!(f, "failed"),
        }
    }
}

// =============================================================================
// Managed Process
// =============================================================================

#[derive(Debug)]
pub struct ManagedProcess {
    pub name: String,
    pub config: ProcessConfig,
    pub state: ProcessState,
    pub pid: Option<u32>,
    pub child: Option<Child>,
    pub started_at: Option<DateTime<Utc>>,
    pub restart_count: u32,
    pub last_exit_code: Option<i32>,
    pub restart_timestamps: Vec<Instant>,
}

impl ManagedProcess {
    pub fn new(name: String, config: ProcessConfig) -> Self {
        Self {
            name,
            config,
            state: ProcessState::Stopped,
            pid: None,
            child: None,
            started_at: None,
            restart_count: 0,
            last_exit_code: None,
            restart_timestamps: Vec::new(),
        }
    }

    pub fn uptime(&self) -> Option<Duration> {
        self.started_at.map(|started| {
            let now = Utc::now();
            let diff = now.signed_duration_since(started);
            Duration::from_secs(diff.num_seconds().max(0) as u64)
        })
    }

    pub fn uptime_display(&self) -> String {
        match self.uptime() {
            Some(d) => {
                let total_secs = d.as_secs();
                let hours = total_secs / 3600;
                let minutes = (total_secs % 3600) / 60;
                let seconds = total_secs % 60;
                if hours > 0 {
                    format!("{}h {}m {}s", hours, minutes, seconds)
                } else if minutes > 0 {
                    format!("{}m {}s", minutes, seconds)
                } else {
                    format!("{}s", seconds)
                }
            }
            None => "-".to_string(),
        }
    }
}

// =============================================================================
// Process Manager
// =============================================================================

pub struct ProcessManager {
    pub processes: HashMap<String, Arc<Mutex<ManagedProcess>>>,
    config: GuardianConfig,
}

impl ProcessManager {
    pub fn new(config: GuardianConfig) -> Self {
        let mut processes = HashMap::new();

        for (name, proc_config) in &config.processes {
            processes.insert(
                name.clone(),
                Arc::new(Mutex::new(ManagedProcess::new(
                    name.clone(),
                    proc_config.clone(),
                ))),
            );
        }

        Self { processes, config }
    }

    /// Start a single process by name
    pub async fn start_process(&self, name: &str) -> Result<()> {
        let proc_arc = self
            .processes
            .get(name)
            .ok_or_else(|| anyhow::anyhow!("Process '{}' not found", name))?
            .clone();

        let mut proc = proc_arc.lock().await;

        if proc.state == ProcessState::Running {
            info!("Process '{}' is already running", name);
            return Ok(());
        }

        proc.state = ProcessState::Starting;
        info!("Starting process '{}'...", name);

        let mut cmd = Command::new(&proc.config.command);
        cmd.args(&proc.config.args);

        // Set working directory
        let work_dir = &proc.config.working_dir;
        if work_dir != "." && Path::new(work_dir).exists() {
            cmd.current_dir(work_dir);
        }

        // Set environment variables
        for (key, value) in &proc.config.env {
            cmd.env(key, value);
        }

        // Redirect stdout/stderr to null to prevent pipe buffer deadlock.
        // Process output is captured via log files configured in health checks.
        cmd.stdout(std::process::Stdio::null());
        cmd.stderr(std::process::Stdio::null());

        // Spawn
        match cmd.spawn() {
            Ok(child) => {
                let pid = child.id();
                proc.pid = pid;
                proc.child = Some(child);
                proc.state = ProcessState::Running;
                proc.started_at = Some(Utc::now());

                info!(
                    "Process '{}' started (PID: {})",
                    name,
                    pid.map(|p| p.to_string())
                        .unwrap_or_else(|| "unknown".to_string())
                );
                Ok(())
            }
            Err(e) => {
                proc.state = ProcessState::Failed;
                error!("Failed to start process '{}': {}", name, e);
                Err(e).with_context(|| format!("Failed to start process '{}'", name))
            }
        }
    }

    /// Stop a single process by name (Sprint 2.6: improved graceful shutdown)
    pub async fn stop_process(&self, name: &str) -> Result<()> {
        self.stop_process_with_grace(name, None).await
    }

    /// Stop a process with a custom grace period
    pub async fn stop_process_with_grace(
        &self,
        name: &str,
        grace_period: Option<u64>,
    ) -> Result<()> {
        let proc_arc = self
            .processes
            .get(name)
            .ok_or_else(|| anyhow::anyhow!("Process '{}' not found", name))?
            .clone();

        let mut proc = proc_arc.lock().await;

        if proc.state == ProcessState::Stopped {
            info!("Process '{}' is already stopped", name);
            return Ok(());
        }

        proc.state = ProcessState::Stopping;
        info!("Stopping process '{}'...", name);

        if let Some(ref mut child) = proc.child {
            let grace = Duration::from_secs(
                grace_period.unwrap_or(self.config.advanced.shutdown_grace_period),
            );

            // Phase 1: Send kill signal (SIGTERM on Unix, TerminateProcess on Windows)
            info!("Sending terminate to process '{}'", name);
            let _ = child.start_kill();

            // Phase 2: Wait for process to exit within grace period
            match tokio::time::timeout(grace, child.wait()).await {
                Ok(Ok(status)) => {
                    proc.last_exit_code = status.code();
                    info!(
                        "Process '{}' stopped gracefully with status: {}",
                        name, status
                    );
                }
                Ok(Err(e)) => {
                    warn!("Error waiting for process '{}': {}", name, e);
                }
                Err(_) => {
                    // Phase 3: Grace period expired - force kill
                    warn!(
                        "Process '{}' did not stop within {}s grace period, force killing",
                        name,
                        grace.as_secs()
                    );
                    let _ = child.kill().await;
                    let _ = child.wait().await;
                    info!("Process '{}' force killed", name);
                }
            }
        }

        proc.state = ProcessState::Stopped;
        proc.pid = None;
        proc.child = None;

        info!("Process '{}' stopped", name);
        Ok(())
    }

    /// Restart a single process
    pub async fn restart_process(&self, name: &str) -> Result<()> {
        info!("Restarting process '{}'...", name);

        self.stop_process(name).await?;

        // Apply restart delay
        let proc_arc = self.processes.get(name).unwrap().clone();
        let delay = {
            let mut proc = proc_arc.lock().await;
            proc.restart_count += 1;
            proc.restart_timestamps.push(Instant::now());
            proc.config.restart_delay
        };

        tokio::time::sleep(Duration::from_secs(delay)).await;

        self.start_process(name).await?;

        Ok(())
    }

    /// Start all processes in dependency order
    pub async fn start_all(&self) -> Result<()> {
        let order = crate::config::topological_sort(&self.config.processes)?;

        info!("Starting processes in order: {:?}", order);

        for name in &order {
            // Start the process
            self.start_process(name).await?;

            // Wait for ready state
            let proc_config = &self.config.processes[name];
            self.wait_for_ready(name, &proc_config.ready).await?;
        }

        info!("All processes started successfully");
        Ok(())
    }

    /// Stop all processes in reverse dependency order
    pub async fn stop_all(&self) -> Result<()> {
        let mut order = crate::config::topological_sort(&self.config.processes)?;
        order.reverse(); // Stop in reverse order

        info!("Stopping processes in order: {:?}", order);

        for name in &order {
            if let Err(e) = self.stop_process(name).await {
                error!("Error stopping process '{}': {}", name, e);
            }
        }

        info!("All processes stopped");
        Ok(())
    }

    /// Wait for a process to become ready
    async fn wait_for_ready(
        &self,
        name: &str,
        ready_config: &crate::config::ReadyConfig,
    ) -> Result<()> {
        let timeout = Duration::from_secs(ready_config.timeout);

        match ready_config.method {
            ReadyMethod::Log => {
                if let Some(ref pattern) = ready_config.pattern {
                    info!(
                        "Waiting for process '{}' to become ready (log pattern: {})",
                        name, pattern
                    );
                    self.wait_for_log_pattern(name, pattern, timeout).await?;
                }
            }
            ReadyMethod::Port => {
                if let Some(port) = ready_config.port {
                    info!(
                        "Waiting for process '{}' to become ready (port: {})",
                        name, port
                    );
                    self.wait_for_port(port, timeout).await?;
                }
            }
            ReadyMethod::Time => {
                let wait_secs = ready_config.timeout.min(10);
                info!(
                    "Waiting {}s for process '{}' to initialize",
                    wait_secs, name
                );
                tokio::time::sleep(Duration::from_secs(wait_secs)).await;
            }
        }

        info!("Process '{}' is ready", name);
        Ok(())
    }

    /// Wait until a log pattern matches
    async fn wait_for_log_pattern(
        &self,
        name: &str,
        pattern: &str,
        timeout: Duration,
    ) -> Result<()> {
        let regex =
            Regex::new(pattern).with_context(|| format!("Invalid regex pattern: {}", pattern))?;
        let start = Instant::now();

        // Get log file path from process health config
        let log_file = {
            let proc_arc = self.processes.get(name).unwrap().clone();
            let proc = proc_arc.lock().await;
            proc.config.health.log_file.clone()
        };

        if let Some(log_path) = log_file {
            let path = Path::new(&log_path);

            // Wait for log file to appear
            while !path.exists() && start.elapsed() < timeout {
                tokio::time::sleep(Duration::from_millis(200)).await;
            }

            if path.exists() {
                // Read log file and check for pattern
                while start.elapsed() < timeout {
                    if let Ok(content) = tokio::fs::read_to_string(path).await {
                        if regex.is_match(&content) {
                            return Ok(());
                        }
                    }
                    tokio::time::sleep(Duration::from_millis(500)).await;
                }
            }
        }

        // Also check stdout of the process
        // For simplicity in this implementation, we fall back to a time-based wait
        // if the log file approach times out
        if start.elapsed() < timeout {
            tokio::time::sleep(Duration::from_secs(3)).await;
        }

        Ok(())
    }

    /// Wait until a TCP port is available
    async fn wait_for_port(&self, port: u16, timeout: Duration) -> Result<()> {
        let start = Instant::now();
        let addr = format!("127.0.0.1:{}", port);

        while start.elapsed() < timeout {
            match tokio::net::TcpStream::connect(&addr).await {
                Ok(_) => return Ok(()),
                Err(_) => {
                    tokio::time::sleep(Duration::from_millis(500)).await;
                }
            }
        }

        anyhow::bail!(
            "Timeout waiting for port {} after {:?}",
            port,
            timeout
        )
    }

    /// Check if a process is still running
    pub async fn is_running(&self, name: &str) -> bool {
        if let Some(proc_arc) = self.processes.get(name) {
            let proc = proc_arc.lock().await;
            proc.state == ProcessState::Running
        } else {
            false
        }
    }

    /// Get process info for status display
    pub async fn get_status(&self) -> Vec<ProcessStatus> {
        let mut statuses = Vec::new();

        for (name, proc_arc) in &self.processes {
            let proc = proc_arc.lock().await;
            statuses.push(ProcessStatus {
                name: name.clone(),
                state: proc.state.clone(),
                pid: proc.pid,
                uptime: proc.uptime_display(),
                restart_count: proc.restart_count,
            });
        }

        statuses.sort_by(|a, b| a.name.cmp(&b.name));
        statuses
    }

    /// Get recent restart count within a time window
    pub async fn recent_restart_count(&self, name: &str, window: Duration) -> u32 {
        if let Some(proc_arc) = self.processes.get(name) {
            let proc = proc_arc.lock().await;
            let cutoff = Instant::now() - window;
            proc.restart_timestamps
                .iter()
                .filter(|t| **t > cutoff)
                .count() as u32
        } else {
            0
        }
    }
}

#[derive(Debug)]
pub struct ProcessStatus {
    pub name: String,
    pub state: ProcessState,
    pub pid: Option<u32>,
    pub uptime: String,
    pub restart_count: u32,
}
