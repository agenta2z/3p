/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

//! Session management commands for the RankEvolve CLI.

use anyhow::Result;
use clap::Args;
use clap::Subcommand;

use crate::client::RankEvolveClient;

#[derive(Subcommand)]
pub enum SessionCommand {
    /// Create a new evolution session
    Create(CreateArgs),
    /// Start a session (from READY state)
    Start(StartArgs),
    /// Pause a running session
    Pause(PauseArgs),
    /// Cancel a session
    Cancel(CancelArgs),
    /// List sessions with optional filters
    List(ListArgs),
    /// Delete a session
    Delete(DeleteArgs),
    /// Show detailed session status
    Status(StatusArgs),
}

#[derive(Args)]
pub struct CreateArgs {
    #[arg(long, short = 'g')]
    pub goal: String,
    #[arg(long, default_value = "default")]
    pub flow_id: String,
    #[arg(long, default_value = "10")]
    pub max_iterations: i32,
    #[arg(long)]
    pub owner_id: Option<String>,
}

#[derive(Args)]
pub struct StartArgs {
    #[arg(long, short = 's')]
    pub session_id: String,
}

#[derive(Args)]
pub struct PauseArgs {
    #[arg(long, short = 's')]
    pub session_id: String,
}

#[derive(Args)]
pub struct CancelArgs {
    #[arg(long, short = 's')]
    pub session_id: String,
    #[arg(long, short = 'r')]
    pub reason: Option<String>,
}

#[derive(Args)]
pub struct ListArgs {
    #[arg(long)]
    pub owner: Option<String>,
    #[arg(long)]
    pub status: Option<Vec<String>>,
    #[arg(long, default_value = "100")]
    pub limit: i32,
}

#[derive(Args)]
pub struct DeleteArgs {
    #[arg(long, short = 's')]
    pub session_id: String,
    #[arg(long, short = 'f')]
    pub force: bool,
}

#[derive(Args)]
pub struct StatusArgs {
    #[arg(long, short = 's')]
    pub session_id: String,
}

pub async fn execute(command: SessionCommand, client: &RankEvolveClient) -> Result<()> {
    match command {
        SessionCommand::Create(args) => execute_create(args, client).await,
        SessionCommand::Start(args) => execute_start(args, client).await,
        SessionCommand::Pause(args) => execute_pause(args, client).await,
        SessionCommand::Cancel(args) => execute_cancel(args, client).await,
        SessionCommand::List(args) => execute_list(args, client).await,
        SessionCommand::Delete(args) => execute_delete(args, client).await,
        SessionCommand::Status(args) => execute_status(args, client).await,
    }
}

async fn execute_create(args: CreateArgs, client: &RankEvolveClient) -> Result<()> {
    println!("Creating session with goal: {}", args.goal);
    let response = client
        .create_session(
            &args.goal,
            Some(&args.flow_id),
            args.max_iterations,
            args.owner_id.as_deref(),
        )
        .await?;
    println!("Session created successfully!");
    println!("   Session ID: {}", response.session_id);
    println!("   Status: {}", response.status);
    println!();
    println!("Next steps:");
    println!(
        "   Start the session: rankevolve session start --session-id {}",
        response.session_id
    );
    Ok(())
}

async fn execute_start(args: StartArgs, client: &RankEvolveClient) -> Result<()> {
    println!("Starting session: {}", args.session_id);
    let response = client.start_session(&args.session_id).await?;
    if response.success {
        println!("Session started successfully!");
        println!("   Status: {}", response.status);
    } else {
        println!("Failed to start session");
        if let Some(err) = response.error_message {
            println!("   Error: {}", err);
        }
    }
    Ok(())
}

async fn execute_pause(args: PauseArgs, client: &RankEvolveClient) -> Result<()> {
    println!("Pausing session: {}", args.session_id);
    let response = client.pause_session(&args.session_id).await?;
    if response.success {
        println!("Session paused successfully!");
        println!("   Status: {}", response.status);
    } else {
        println!("Failed to pause session");
    }
    Ok(())
}

async fn execute_cancel(args: CancelArgs, client: &RankEvolveClient) -> Result<()> {
    println!("Cancelling session: {}", args.session_id);
    let response = client
        .cancel_session(&args.session_id, args.reason.as_deref())
        .await?;
    if response.success {
        println!("Session cancelled successfully!");
        println!("   Status: {}", response.status);
    } else {
        println!("Failed to cancel session");
    }
    Ok(())
}

async fn execute_list(args: ListArgs, client: &RankEvolveClient) -> Result<()> {
    let response = client
        .list_sessions(args.owner.as_deref(), args.status, args.limit, 0)
        .await?;
    if response.sessions.is_empty() {
        println!("No sessions found.");
        return Ok(());
    }
    println!("Sessions ({} total):", response.total_count);
    println!();
    println!(
        "{:<40} {:<12} {:<8} {:<20}",
        "Session ID", "Status", "Iter", "Research Goal"
    );
    println!("{}", "-".repeat(80));
    for session in response.sessions {
        let goal_truncated = if session.research_goal.len() > 20 {
            format!("{}...", &session.research_goal[..17])
        } else {
            session.research_goal.clone()
        };
        println!(
            "{:<40} {:<12} {:<8} {:<20}",
            session.session_id, session.status, session.current_iteration, goal_truncated
        );
    }
    Ok(())
}

async fn execute_delete(args: DeleteArgs, client: &RankEvolveClient) -> Result<()> {
    if !args.force {
        println!(
            "Warning: This will permanently delete session {}",
            args.session_id
        );
        println!("   Use --force to confirm deletion.");
        return Ok(());
    }
    println!("Deleting session: {}", args.session_id);
    let success = client.delete_session(&args.session_id).await?;
    if success {
        println!("Session deleted successfully!");
    } else {
        println!("Failed to delete session");
    }
    Ok(())
}

async fn execute_status(args: StatusArgs, client: &RankEvolveClient) -> Result<()> {
    let session = client.get_session(&args.session_id).await?;
    println!("Session Status");
    println!("{}", "=".repeat(60));
    println!();
    println!("Session ID:      {}", session.session_id);
    println!("Flow ID:         {}", session.flow_id);
    println!("Status:          {}", session.status);
    println!("Current Iter:    {}", session.current_iteration);
    println!("Owner:           {}", session.owner_id);
    println!("Research Goal:   {}", session.research_goal);
    if let Some(step_id) = &session.current_step_id {
        println!("Current Step:    {}", step_id);
    }
    if let Some(error) = &session.error_message {
        println!();
        println!("Error: {}", error);
    }
    Ok(())
}
