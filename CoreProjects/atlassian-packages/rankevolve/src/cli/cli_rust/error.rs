/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

//! Error handling for the RankEvolve CLI.

use std::fmt;

#[derive(Debug)]
pub enum CliError {
    SessionNotFound(String),
    InvalidStateTransition(String),
    InterventionNotFound(String),
    InterventionTimeout(String),
    FlowValidationFailed(String),
    AgentError(String),
    PermissionDenied(String),
    RateLimited(String),
    ConnectionFailed(String),
    ConfigError(String),
    ServerError(String),
    Unknown(String),
}

impl fmt::Display for CliError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            CliError::SessionNotFound(msg) => {
                write!(
                    f,
                    "Session not found. Use 'rankevolve session list' to see available sessions. {}",
                    msg
                )
            }
            CliError::InvalidStateTransition(msg) => {
                write!(f, "Invalid operation for current session state: {}", msg)
            }
            CliError::InterventionNotFound(msg) => {
                write!(f, "Intervention not found or already responded. {}", msg)
            }
            CliError::InterventionTimeout(msg) => {
                write!(f, "Intervention timed out. {}", msg)
            }
            CliError::FlowValidationFailed(msg) => {
                write!(f, "Flow configuration invalid: {}", msg)
            }
            CliError::AgentError(msg) => {
                write!(f, "Agent execution error: {}", msg)
            }
            CliError::PermissionDenied(msg) => {
                write!(f, "Permission denied. {}", msg)
            }
            CliError::RateLimited(msg) => {
                write!(f, "Rate limited. Please try again later. {}", msg)
            }
            CliError::ConnectionFailed(msg) => {
                write!(f, "Failed to connect to server: {}", msg)
            }
            CliError::ConfigError(msg) => {
                write!(f, "Configuration error: {}", msg)
            }
            CliError::ServerError(msg) => {
                write!(f, "Server error: {}", msg)
            }
            CliError::Unknown(msg) => {
                write!(f, "Unknown error: {}", msg)
            }
        }
    }
}

impl std::error::Error for CliError {}

impl From<anyhow::Error> for CliError {
    fn from(err: anyhow::Error) -> Self {
        CliError::Unknown(err.to_string())
    }
}

pub type CliResult<T> = Result<T, CliError>;
