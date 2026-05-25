/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

//! RankEvolve CLI - Command line interface for RankEvolve.

use anyhow::Result;
use clap::Parser;
use clap::Subcommand;
use rankevolve_cli_lib::client::RankEvolveClient;
use rankevolve_cli_lib::commands::session::SessionCommand;
use rankevolve_cli_lib::commands::session::{self};
use rankevolve_cli_lib::config::ClientConfig;
use tracing_subscriber::EnvFilter;

#[derive(Parser)]
#[command(
    name = "rankevolve",
    about = "RankEvolve CLI - Automated model optimization through evolution",
    version = "0.1.0"
)]
struct Cli {
    #[arg(long, short = 's', default_value = "localhost:9090")]
    server: String,

    #[arg(long, short = 'v', global = true)]
    verbose: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Session lifecycle management
    Session {
        #[command(subcommand)]
        command: SessionCommand,
    },
    /// Health check
    Health,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    let filter = if cli.verbose {
        EnvFilter::new("debug")
    } else {
        EnvFilter::new("info")
    };

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .init();

    let config = ClientConfig::load()?.with_server_address(cli.server);
    let client = RankEvolveClient::connect(config).await?;

    match cli.command {
        Commands::Session { command } => {
            session::execute(command, &client).await?;
        }
        Commands::Health => {
            let healthy = client.health_check().await?;
            if healthy {
                println!("Server is healthy");
            } else {
                println!("Server is unhealthy");
                std::process::exit(1);
            }
        }
    }

    Ok(())
}
