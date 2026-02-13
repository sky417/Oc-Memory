use anyhow::Result;
use tracing_subscriber::{fmt, EnvFilter};

use crate::config::LoggingConfig;

/// Initialize the tracing/logging subsystem
pub fn init_logging(config: &LoggingConfig) -> Result<()> {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new(&config.level));

    let subscriber = fmt()
        .with_env_filter(filter)
        .with_target(true)
        .with_thread_ids(false)
        .with_file(false)
        .with_line_number(false);

    if config.format == "json" {
        subscriber.json().init();
    } else {
        subscriber.init();
    }

    Ok(())
}
