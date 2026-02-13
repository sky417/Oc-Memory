#![allow(dead_code)]

mod compression;
mod config;
mod health;
mod log_rotation;
mod logger;
mod macos;
mod notification;
mod process;
mod recovery;

use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::Colorize;
use comfy_table::{modifiers::UTF8_ROUND_CORNERS, presets::UTF8_FULL, Cell, Color, Table};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;
use tracing::{error, info, warn};

use crate::compression::CompressionManager;
use crate::config::{load_config, GuardianConfig};
use crate::health::{HealthChecker, HealthStatus};
use crate::log_rotation::LogRotator;
use crate::macos::SleepPreventer;
use crate::notification::{EventType, NotificationEvent, NotificationManager, Severity};
use crate::process::{ProcessManager, ProcessState};
use crate::recovery::RecoveryEngine;

// =============================================================================
// CLI Definition
// =============================================================================

#[derive(Parser)]
#[command(
    name = "oc-guardian",
    about = "OpenClaw Process Guardian - Manages OpenClaw and OC-Memory processes",
    version
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    /// Path to guardian.toml configuration file
    #[arg(short, long, default_value = "guardian.toml")]
    config: String,
}

#[derive(Subcommand)]
enum Commands {
    /// Start all managed processes in dependency order
    Start,

    /// Stop all managed processes gracefully
    Stop,

    /// Restart a specific process or all processes
    Restart {
        /// Process name to restart (all if omitted)
        process: Option<String>,
    },

    /// Show status of all managed processes
    Status,

    /// View logs for a specific process
    Logs {
        /// Process name to view logs for
        process: Option<String>,

        /// Follow log output (like tail -f)
        #[arg(short, long)]
        follow: bool,

        /// Number of last lines to show
        #[arg(short = 'n', long, default_value = "50")]
        tail: usize,
    },
}

// =============================================================================
// Main
// =============================================================================

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Load configuration
    let config_path = PathBuf::from(&cli.config);
    let config = load_config(&config_path)?;

    // Initialize logging
    logger::init_logging(&config.logging)?;

    info!("OC-Guardian starting with config: {}", cli.config);

    // Execute command
    match cli.command {
        Commands::Start => handle_start(config).await?,
        Commands::Stop => handle_stop(config).await?,
        Commands::Restart { process } => handle_restart(config, process).await?,
        Commands::Status => handle_status(config).await?,
        Commands::Logs {
            process,
            follow,
            tail,
        } => handle_logs(config, process, follow, tail).await?,
    }

    Ok(())
}

// =============================================================================
// Command Handlers
// =============================================================================

async fn handle_start(config: GuardianConfig) -> Result<()> {
    println!("{}", "Starting OC-Guardian...".green().bold());

    let manager = ProcessManager::new(config.clone());

    // Start all processes in dependency order
    manager.start_all().await?;

    println!("{}", "All processes started successfully!".green().bold());

    // Enter supervisor loop
    supervisor_loop(config, manager).await
}

async fn handle_stop(config: GuardianConfig) -> Result<()> {
    println!("{}", "Stopping all processes...".yellow().bold());

    // Discover running processes by command name and terminate them
    let mut sys = sysinfo::System::new_all();
    sys.refresh_processes();
    let mut stopped = 0;

    for (name, proc_config) in &config.processes {
        // Extract the command basename to match against running processes
        let cmd_name = std::path::Path::new(&proc_config.command)
            .file_name()
            .and_then(|f| f.to_str())
            .unwrap_or(&proc_config.command)
            .to_string();

        for (_pid, process) in sys.processes() {
            let proc_name = process.name();
            if proc_name.contains(&cmd_name) {
                info!("Stopping process '{}' (PID: {})", name, _pid);
                process.kill();
                stopped += 1;
                break;
            }
        }
    }

    if stopped == 0 {
        println!("{}", "No running processes found.".yellow());
    } else {
        println!(
            "{}",
            format!("{} process(es) stopped.", stopped).green()
        );
    }

    Ok(())
}

async fn handle_restart(config: GuardianConfig, process: Option<String>) -> Result<()> {
    let manager = ProcessManager::new(config);

    match process {
        Some(name) => {
            println!("Restarting process '{}'...", name);
            manager.restart_process(&name).await?;
            println!("{}", format!("Process '{}' restarted.", name).green());
        }
        None => {
            println!("{}", "Restarting all processes...".yellow());
            manager.stop_all().await?;
            manager.start_all().await?;
            println!("{}", "All processes restarted.".green());
        }
    }

    Ok(())
}

async fn handle_status(config: GuardianConfig) -> Result<()> {
    // Discover actual running processes via sysinfo
    let mut sys = sysinfo::System::new_all();
    sys.refresh_processes();

    let mut table = Table::new();
    table
        .load_preset(UTF8_FULL)
        .apply_modifier(UTF8_ROUND_CORNERS)
        .set_header(vec![
            Cell::new("Name").fg(Color::White),
            Cell::new("Status").fg(Color::White),
            Cell::new("PID").fg(Color::White),
            Cell::new("Command").fg(Color::White),
        ]);

    for (name, proc_config) in &config.processes {
        let cmd_name = std::path::Path::new(&proc_config.command)
            .file_name()
            .and_then(|f| f.to_str())
            .unwrap_or(&proc_config.command)
            .to_string();

        let mut found = false;
        for (pid, process) in sys.processes() {
            let proc_name = process.name();
            if proc_name.contains(&cmd_name) {
                table.add_row(vec![
                    Cell::new(name),
                    Cell::new("online").fg(Color::Green),
                    Cell::new(pid.to_string()),
                    Cell::new(&proc_config.command),
                ]);
                found = true;
                break;
            }
        }

        if !found {
            table.add_row(vec![
                Cell::new(name),
                Cell::new("stopped").fg(Color::DarkGrey),
                Cell::new("-"),
                Cell::new(&proc_config.command),
            ]);
        }
    }

    println!("{}", table);
    Ok(())
}

async fn handle_logs(
    config: GuardianConfig,
    process: Option<String>,
    follow: bool,
    tail: usize,
) -> Result<()> {
    // Determine which log file to read
    let log_file = match process {
        Some(ref name) => {
            if let Some(proc_config) = config.processes.get(name) {
                proc_config
                    .health
                    .log_file
                    .clone()
                    .unwrap_or_else(|| format!("{}.log", name))
            } else {
                anyhow::bail!("Process '{}' not found", name);
            }
        }
        None => config.logging.output.clone(),
    };

    let path = std::path::Path::new(&log_file);
    if !path.exists() {
        println!("Log file not found: {}", log_file);
        return Ok(());
    }

    // Read last N lines
    let content = std::fs::read_to_string(path)?;
    let lines: Vec<&str> = content.lines().collect();
    let start = if lines.len() > tail {
        lines.len() - tail
    } else {
        0
    };

    for line in &lines[start..] {
        println!("{}", line);
    }

    if follow {
        println!("{}", "--- Following log output (Ctrl+C to stop) ---".dimmed());

        // Simple follow: poll for new content
        let mut last_len = content.len();
        loop {
            tokio::time::sleep(Duration::from_millis(500)).await;

            if let Ok(new_content) = std::fs::read_to_string(path) {
                if new_content.len() > last_len {
                    let new_part = &new_content[last_len..];
                    print!("{}", new_part);
                    last_len = new_content.len();
                }
            }
        }
    }

    Ok(())
}

// =============================================================================
// Supervisor Main Loop (Phase 3: with log rotation, compression, sleep, notifications)
// =============================================================================

async fn supervisor_loop(config: GuardianConfig, manager: ProcessManager) -> Result<()> {
    let interval = Duration::from_secs(config.advanced.supervisor_interval);
    let mut health_checker = HealthChecker::new();
    let mut recovery_engine = RecoveryEngine::new(config.recovery.clone());

    // Phase 3 subsystems
    let mut log_rotator = LogRotator::new(config.logging.clone());
    let mut compression_manager =
        CompressionManager::new(config.memory.compression.clone());
    let mut sleep_preventer = SleepPreventer::new(config.macos.clone());
    let mut notifier = NotificationManager::new(config.notifications.clone());

    info!("Supervisor loop started (interval: {:?})", interval);
    println!(
        "{}",
        "Supervisor active. Press Ctrl+C to stop.".dimmed()
    );

    // Start macOS sleep prevention
    if let Err(e) = sleep_preventer.start().await {
        warn!("Failed to start sleep prevention: {}", e);
    }

    // Send startup notification
    let _ = notifier
        .notify(&NotificationEvent {
            event_type: EventType::GuardianStartup,
            process_name: "guardian".to_string(),
            message: "OC-Guardian supervisor started".to_string(),
            severity: Severity::Info,
        })
        .await;

    // Handle Ctrl+C gracefully
    let running = Arc::new(Mutex::new(true));
    let running_clone = running.clone();

    tokio::spawn(async move {
        tokio::signal::ctrl_c().await.ok();
        info!("Received shutdown signal (Ctrl+C)");
        println!(
            "\n{}",
            "Shutting down gracefully...".yellow().bold()
        );
        *running_clone.lock().await = false;
    });

    let mut check_count: u64 = 0;
    let log_rotation_interval = 3600; // 1 hour in seconds

    loop {
        // Check if we should stop
        if !*running.lock().await {
            info!("Supervisor shutting down...");

            // Stop macOS sleep prevention
            if let Err(e) = sleep_preventer.stop().await {
                warn!("Failed to stop sleep prevention: {}", e);
            }

            // Stop all processes in reverse dependency order
            println!("{}", "Stopping all processes in dependency order...".yellow());
            manager.stop_all().await?;

            // Log final recovery stats
            let stats = recovery_engine.stats();
            info!(
                "Final recovery stats: total={}, successful={}, failed={}",
                stats.total_recoveries, stats.successful, stats.failed
            );

            // Log compression stats
            let comp_history = compression_manager.history();
            if comp_history.total_compressions() > 0 {
                info!(
                    "Compression stats: total={}, successful={}, avg_ratio={:.1}x",
                    comp_history.total_compressions(),
                    comp_history.successful_compressions(),
                    comp_history.average_ratio()
                );
            }

            // Send shutdown notification
            let _ = notifier
                .notify(&NotificationEvent {
                    event_type: EventType::GuardianShutdown,
                    process_name: "guardian".to_string(),
                    message: "OC-Guardian supervisor stopped".to_string(),
                    severity: Severity::Info,
                })
                .await;

            println!("{}", "All processes stopped. Goodbye!".green());
            break;
        }

        check_count += 1;

        // Health check each process
        for (name, proc_arc) in &manager.processes {
            let proc = proc_arc.lock().await;

            if proc.state != ProcessState::Running {
                // Check if process was supposed to be running but died
                if proc.state == ProcessState::Failed && proc.config.auto_restart {
                    let restart_count = proc.restart_count;
                    drop(proc);

                    info!("Process '{}' is in Failed state, attempting restart", name);

                    // Send crash notification
                    let _ = notifier
                        .notify(&NotificationEvent {
                            event_type: EventType::ProcessCrash,
                            process_name: name.clone(),
                            message: format!("Process '{}' crashed, attempting recovery", name),
                            severity: Severity::Critical,
                        })
                        .await;

                    if let Some(action) = recovery_engine.evaluate(
                        name,
                        &health::HealthCheckResult {
                            process_name: name.clone(),
                            status: HealthStatus::Unhealthy("Process failed".to_string()),
                            level_results: vec![health::LevelResult {
                                level: 1,
                                name: "Process Alive".to_string(),
                                passed: false,
                                message: "Process in Failed state".to_string(),
                            }],
                            checked_at: std::time::Instant::now(),
                        },
                        restart_count,
                    ) {
                        if let Err(e) = recovery_engine.execute(&action, name, &manager).await {
                            error!("Recovery failed for '{}': {}", name, e);
                        }
                    }
                    continue;
                }

                continue;
            }

            let health_config = proc.config.health.clone();
            let pid = proc.pid;
            let restart_count = proc.restart_count;
            drop(proc);

            // Run health checks
            let health_result = health_checker
                .check_process(name, pid, &health_config)
                .await;

            // Evaluate recovery if needed
            if health_result.status != HealthStatus::Healthy {
                warn!(
                    "Process '{}' health: {}",
                    name, health_result.status
                );

                // Notify about health check failure
                let _ = notifier
                    .notify(&NotificationEvent {
                        event_type: EventType::HealthCheckFailed,
                        process_name: name.clone(),
                        message: format!(
                            "Health check failed: {}",
                            health_result.status
                        ),
                        severity: Severity::Warning,
                    })
                    .await;

                if let Some(action) = recovery_engine.evaluate(name, &health_result, restart_count)
                {
                    info!("Recovery action for '{}': {}", name, action);

                    if let Err(e) = recovery_engine.execute(&action, name, &manager).await {
                        error!("Recovery failed for '{}': {}", name, e);
                    }
                }
            }
        }

        // Log rotation check (every hour)
        if log_rotator.should_check(log_rotation_interval) {
            match log_rotator.rotate_if_needed() {
                Ok(stats) => {
                    if stats.files_rotated > 0 {
                        info!(
                            "Log rotation: {} files rotated ({} checked, {} errors)",
                            stats.files_rotated, stats.files_checked, stats.errors
                        );
                    }
                }
                Err(e) => {
                    error!("Log rotation failed: {}", e);
                }
            }
        }

        // Memory compression check (every check cycle)
        match compression_manager.check_and_compress().await {
            Ok(Some(result)) => {
                info!(
                    "Compression completed: {:.1}x ratio, {} tokens -> {} tokens",
                    result.compression_ratio, result.tokens_before, result.tokens_after
                );

                let _ = notifier
                    .notify(&NotificationEvent {
                        event_type: EventType::CompressionComplete,
                        process_name: "guardian".to_string(),
                        message: format!(
                            "Memory compression: {:.1}x ratio ({} -> {} tokens)",
                            result.compression_ratio, result.tokens_before, result.tokens_after
                        ),
                        severity: Severity::Info,
                    })
                    .await;
            }
            Ok(None) => {}
            Err(e) => {
                error!("Compression check failed: {}", e);
            }
        }

        // Periodic stats logging (every 60 checks)
        if check_count % 60 == 0 {
            let stats = recovery_engine.stats();
            if stats.total_recoveries > 0 {
                info!(
                    "Recovery stats: total={}, ok={}, failed={}, scenarios={:?}",
                    stats.total_recoveries, stats.successful, stats.failed, stats.by_scenario
                );
            }

            let notif_stats = notifier.stats();
            if notif_stats.total_sent > 0 {
                info!("Notification stats: total_sent={}", notif_stats.total_sent);
            }
        }

        tokio::time::sleep(interval).await;
    }

    Ok(())
}
