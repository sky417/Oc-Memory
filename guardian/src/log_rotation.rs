use anyhow::{Context, Result};
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::Instant;
use tracing::{error, info};

use crate::config::LoggingConfig;

// =============================================================================
// Log Rotator (Sprint 3.3)
// =============================================================================

pub struct LogRotator {
    config: LoggingConfig,
    last_rotation: Option<Instant>,
}

impl LogRotator {
    pub fn new(config: LoggingConfig) -> Self {
        Self {
            config,
            last_rotation: None,
        }
    }

    /// Check and rotate all managed log files
    pub fn rotate_if_needed(&mut self) -> Result<RotationStats> {
        let mut stats = RotationStats::default();

        // Collect log files to rotate
        let mut files_to_rotate: Vec<LogFileInfo> = Vec::new();

        // Guardian's own log
        files_to_rotate.push(LogFileInfo {
            path: self.config.output.clone(),
            max_size: parse_size(&self.config.max_size),
            max_files: self.config.max_files,
            compress: true,
        });

        // Managed log files
        for managed in &self.config.managed_logs.files {
            files_to_rotate.push(LogFileInfo {
                path: managed.path.clone(),
                max_size: parse_size(&managed.max_size),
                max_files: managed.max_files,
                compress: true,
            });
        }

        // Rotate each file
        for file_info in &files_to_rotate {
            match self.rotate_file(file_info) {
                Ok(rotated) => {
                    if rotated {
                        stats.files_rotated += 1;
                        info!("Rotated log file: {}", file_info.path);
                    }
                    stats.files_checked += 1;
                }
                Err(e) => {
                    stats.errors += 1;
                    error!("Failed to rotate {}: {}", file_info.path, e);
                }
            }
        }

        self.last_rotation = Some(Instant::now());
        Ok(stats)
    }

    /// Rotate a single log file if it exceeds max_size
    fn rotate_file(&self, info: &LogFileInfo) -> Result<bool> {
        let path = Path::new(&info.path);
        if !path.exists() {
            return Ok(false);
        }

        let metadata = fs::metadata(path)
            .with_context(|| format!("Failed to get metadata for {}", info.path))?;

        let file_size = metadata.len();

        // Check if rotation is needed
        if file_size < info.max_size {
            return Ok(false);
        }

        info!(
            "Log file {} is {}MB (max: {}MB), rotating...",
            info.path,
            file_size / (1024 * 1024),
            info.max_size / (1024 * 1024)
        );

        // Shift existing rotated files (file.log.5.gz -> deleted, file.log.4.gz -> file.log.5.gz, etc.)
        self.shift_rotated_files(path, info.max_files)?;

        // Compress current file to file.log.1.gz
        if info.compress {
            self.compress_and_rotate(path)?;
        } else {
            self.rename_rotate(path)?;
        }

        // Create fresh empty log file
        fs::write(path, "")
            .with_context(|| format!("Failed to create empty log file: {}", info.path))?;

        Ok(true)
    }

    /// Shift rotated files: N -> N+1, delete if N >= max_files
    fn shift_rotated_files(&self, base_path: &Path, max_files: u32) -> Result<()> {
        // Delete the oldest if it exists
        let oldest = rotated_path(base_path, max_files, true);
        if oldest.exists() {
            fs::remove_file(&oldest)?;
        }

        // Shift from max_files-1 down to 1
        for i in (1..max_files).rev() {
            let from = rotated_path(base_path, i, true);
            let to = rotated_path(base_path, i + 1, true);
            if from.exists() {
                fs::rename(&from, &to)?;
            }

            // Also check uncompressed
            let from_plain = rotated_path(base_path, i, false);
            let to_plain = rotated_path(base_path, i + 1, false);
            if from_plain.exists() {
                fs::rename(&from_plain, &to_plain)?;
            }
        }

        Ok(())
    }

    /// Compress the current log file to .1.gz using miniz_oxide (pure Rust deflate)
    fn compress_and_rotate(&self, path: &Path) -> Result<()> {
        let dest = rotated_path(path, 1, true);

        // Read original file
        let mut original = fs::File::open(path)
            .with_context(|| format!("Failed to open log file: {}", path.display()))?;
        let mut content = Vec::new();
        original.read_to_end(&mut content)?;

        // Gzip compression using miniz_oxide
        let compressed = simple_compress(&content);

        let mut dest_file = fs::File::create(&dest)
            .with_context(|| format!("Failed to create rotated file: {}", dest.display()))?;
        dest_file.write_all(&compressed)?;

        info!(
            "Compressed {} -> {} ({}% reduction)",
            path.display(),
            dest.display(),
            if content.is_empty() {
                0
            } else {
                100 - (compressed.len() * 100 / content.len())
            }
        );

        Ok(())
    }

    /// Simple rename-based rotation (no compression)
    fn rename_rotate(&self, path: &Path) -> Result<()> {
        let dest = rotated_path(path, 1, false);
        fs::copy(path, &dest)?;
        Ok(())
    }

    /// Check if rotation interval has elapsed (default: 1 hour)
    pub fn should_check(&self, interval_secs: u64) -> bool {
        match self.last_rotation {
            Some(last) => last.elapsed().as_secs() >= interval_secs,
            None => true,
        }
    }
}

// =============================================================================
// Helper Functions
// =============================================================================

/// Generate rotated file path: file.log.N or file.log.N.gz
fn rotated_path(base: &Path, generation: u32, compressed: bool) -> PathBuf {
    let base_str = base.to_string_lossy();
    if compressed {
        PathBuf::from(format!("{}.{}.gz", base_str, generation))
    } else {
        PathBuf::from(format!("{}.{}", base_str, generation))
    }
}

/// Parse size string like "50MB", "1GB", "100KB" into bytes
fn parse_size(size_str: &str) -> u64 {
    let size_str = size_str.trim().to_uppercase();

    if let Some(num) = size_str.strip_suffix("GB") {
        num.trim().parse::<u64>().unwrap_or(1) * 1024 * 1024 * 1024
    } else if let Some(num) = size_str.strip_suffix("MB") {
        num.trim().parse::<u64>().unwrap_or(50) * 1024 * 1024
    } else if let Some(num) = size_str.strip_suffix("KB") {
        num.trim().parse::<u64>().unwrap_or(1024) * 1024
    } else {
        // Default: try to parse as bytes, fallback to 50MB
        size_str.parse::<u64>().unwrap_or(50 * 1024 * 1024)
    }
}

/// Compress data using miniz_oxide (pure Rust deflate, no external C dependency).
/// Wraps in a minimal gzip container so the output is valid .gz format.
fn simple_compress(data: &[u8]) -> Vec<u8> {
    // Use raw deflate compression at default level
    let compressed = miniz_oxide::deflate::compress_to_vec(data, 6);

    // Build a minimal gzip file: header + compressed + crc32 + size
    let mut gzip = Vec::with_capacity(10 + compressed.len() + 8);

    // Gzip header (10 bytes, minimal)
    gzip.extend_from_slice(&[
        0x1f, 0x8b, // magic
        0x08, // method: deflate
        0x00, // flags: none
        0x00, 0x00, 0x00, 0x00, // mtime: 0
        0x00, // extra flags
        0xff, // OS: unknown
    ]);

    // Compressed data (raw deflate)
    gzip.extend_from_slice(&compressed);

    // CRC32 of original data
    let crc = crc32_simple(data);
    gzip.extend_from_slice(&crc.to_le_bytes());

    // Original size mod 2^32
    gzip.extend_from_slice(&(data.len() as u32).to_le_bytes());

    gzip
}

/// Simple CRC32 (IEEE) implementation for gzip trailer
fn crc32_simple(data: &[u8]) -> u32 {
    let mut crc: u32 = 0xFFFFFFFF;
    for &byte in data {
        crc ^= byte as u32;
        for _ in 0..8 {
            if crc & 1 != 0 {
                crc = (crc >> 1) ^ 0xEDB88320;
            } else {
                crc >>= 1;
            }
        }
    }
    !crc
}

// =============================================================================
// Rotation Stats
// =============================================================================

#[derive(Debug, Default)]
pub struct RotationStats {
    pub files_checked: u32,
    pub files_rotated: u32,
    pub errors: u32,
}

struct LogFileInfo {
    path: String,
    max_size: u64,
    max_files: u32,
    compress: bool,
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_size_mb() {
        assert_eq!(parse_size("50MB"), 50 * 1024 * 1024);
        assert_eq!(parse_size("100MB"), 100 * 1024 * 1024);
    }

    #[test]
    fn test_parse_size_gb() {
        assert_eq!(parse_size("1GB"), 1024 * 1024 * 1024);
    }

    #[test]
    fn test_parse_size_kb() {
        assert_eq!(parse_size("512KB"), 512 * 1024);
    }

    #[test]
    fn test_parse_size_case_insensitive() {
        assert_eq!(parse_size("50mb"), 50 * 1024 * 1024);
        assert_eq!(parse_size("1gb"), 1024 * 1024 * 1024);
    }

    #[test]
    fn test_rotated_path_compressed() {
        let base = Path::new("/var/log/guardian.log");
        let result = rotated_path(base, 1, true);
        assert_eq!(result.to_string_lossy(), "/var/log/guardian.log.1.gz");
    }

    #[test]
    fn test_rotated_path_uncompressed() {
        let base = Path::new("/var/log/guardian.log");
        let result = rotated_path(base, 3, false);
        assert_eq!(result.to_string_lossy(), "/var/log/guardian.log.3");
    }

    #[test]
    fn test_log_rotation_basic() {
        let dir = tempfile::tempdir().unwrap();
        let log_path = dir.path().join("test.log");

        // Create a log file larger than threshold
        let content = "A".repeat(1024 * 1024); // 1MB
        fs::write(&log_path, &content).unwrap();

        let config = LoggingConfig {
            output: log_path.to_string_lossy().to_string(),
            max_size: "512KB".to_string(), // Smaller than file
            max_files: 3,
            ..Default::default()
        };

        let mut rotator = LogRotator::new(config);
        let stats = rotator.rotate_if_needed().unwrap();

        assert_eq!(stats.files_rotated, 1);

        // Original file should be empty now
        let new_content = fs::read_to_string(&log_path).unwrap();
        assert!(new_content.is_empty());

        // Rotated file should exist
        let rotated = rotated_path(&log_path, 1, true);
        assert!(rotated.exists());
    }

    #[test]
    fn test_no_rotation_needed() {
        let dir = tempfile::tempdir().unwrap();
        let log_path = dir.path().join("small.log");

        // Create a small file
        fs::write(&log_path, "small content").unwrap();

        let config = LoggingConfig {
            output: log_path.to_string_lossy().to_string(),
            max_size: "50MB".to_string(),
            max_files: 3,
            ..Default::default()
        };

        let mut rotator = LogRotator::new(config);
        let stats = rotator.rotate_if_needed().unwrap();

        assert_eq!(stats.files_rotated, 0);
    }

    #[test]
    fn test_generational_shift() {
        let dir = tempfile::tempdir().unwrap();
        let log_path = dir.path().join("shift.log");

        // Create main file and rotated files
        fs::write(&log_path, "A".repeat(1024 * 1024)).unwrap();
        let gen1 = rotated_path(&log_path, 1, true);
        let gen2 = rotated_path(&log_path, 2, true);
        fs::write(&gen1, "gen1").unwrap();
        fs::write(&gen2, "gen2").unwrap();

        let config = LoggingConfig {
            output: log_path.to_string_lossy().to_string(),
            max_size: "512KB".to_string(),
            max_files: 3,
            ..Default::default()
        };

        let mut rotator = LogRotator::new(config);
        rotator.rotate_if_needed().unwrap();

        // gen1 -> gen2, gen2 -> gen3, new gen1 created
        let gen3 = rotated_path(&log_path, 3, true);
        assert!(gen3.exists());
    }

    #[test]
    fn test_should_check_interval() {
        let config = LoggingConfig::default();
        let rotator = LogRotator::new(config);

        // First check should always return true
        assert!(rotator.should_check(3600));
    }
}
