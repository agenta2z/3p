/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

//! CLI configuration module.

use std::path::PathBuf;

use anyhow::Result;
use serde::Deserialize;
use serde::Serialize;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientConfig {
    pub server_address: String,
    #[serde(default = "default_timeout")]
    pub timeout_seconds: u64,
    #[serde(default = "default_retries")]
    pub max_retries: u32,
    #[serde(default = "default_data_dir")]
    pub data_dir: PathBuf,
}

fn default_timeout() -> u64 {
    30
}

fn default_retries() -> u32 {
    3
}

fn default_data_dir() -> PathBuf {
    std::env::var("HOME")
        .map(|h| {
            PathBuf::from(h)
                .join(".local")
                .join("share")
                .join("rankevolve")
        })
        .unwrap_or_else(|_| PathBuf::from(".").join("rankevolve"))
}

fn config_dir() -> Option<PathBuf> {
    std::env::var("HOME")
        .map(|h| PathBuf::from(h).join(".config"))
        .ok()
}

impl Default for ClientConfig {
    fn default() -> Self {
        Self {
            server_address: "localhost:9090".to_string(),
            timeout_seconds: default_timeout(),
            max_retries: default_retries(),
            data_dir: default_data_dir(),
        }
    }
}

impl ClientConfig {
    pub fn load() -> Result<Self> {
        if let Ok(config_path) = std::env::var("RANKEVOLVE_CONFIG") {
            return Self::load_from_file(&PathBuf::from(config_path));
        }

        if let Some(cfg_dir) = config_dir() {
            let config_path = cfg_dir.join("rankevolve").join("config.json");
            if config_path.exists() {
                return Self::load_from_file(&config_path);
            }
        }

        Ok(Self::default())
    }

    pub fn load_from_file(path: &PathBuf) -> Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: Self = serde_json::from_str(&content)?;
        Ok(config)
    }

    pub fn with_server_address(mut self, address: String) -> Self {
        self.server_address = address;
        self
    }
}
