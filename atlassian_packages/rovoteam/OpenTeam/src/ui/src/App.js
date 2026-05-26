/**
 * OpenStartup — AI Company Dashboard
 *
 * Top-level app shell with sidebar, tab navigation, drill-down views,
 * and bottom bar. Layout:
 *
 * ┌──────────┬──────────────────────────────────────────┐
 * │ Sidebar  │ Header (AppBar with title)               │
 * │ (250px)  │──────────────────────────────────────────│
 * │          │ Tabs (Team | Projects | Tasks | Emps)    │
 * │ Manager  │──────────────────────────────────────────│
 * │ Sessions │                                          │
 * │          │ Active View Content (scrollable)          │
 * │          │                                          │
 * │──────────│──────────────────────────────────────────│
 * │ Settings │ Bottom Bar                               │
 * │ Debug    │                                          │
 * └──────────┴──────────────────────────────────────────┘
 */

import React, { useState } from 'react';
import Box from '@mui/material/Box';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import GroupsIcon from '@mui/icons-material/Groups';
import FolderIcon from '@mui/icons-material/Folder';
import TaskAltIcon from '@mui/icons-material/TaskAlt';
import PeopleIcon from '@mui/icons-material/People';
import AddIcon from '@mui/icons-material/Add';
import SettingsIcon from '@mui/icons-material/Settings';
import BugReportIcon from '@mui/icons-material/BugReport';

import Sidebar from './components/layout/Sidebar';
import TeamOverviewView from './components/views/TeamOverviewView';
import ProjectsView from './components/views/ProjectsView';
import TasksView from './components/views/TasksView';
import EmployeesView from './components/views/EmployeesView';
import SprintBoardView from './components/views/SprintBoardView';
import EmployeeDetailView from './components/views/EmployeeDetailView';
import ConversationView from './components/views/ConversationView';
import ManagerChatView from './components/views/ManagerChatView';

const TABS = [
  { id: 'team-overview', label: 'Team Overview', icon: <GroupsIcon /> },
  { id: 'projects', label: 'Projects', icon: <FolderIcon /> },
  { id: 'tasks', label: 'Tasks', icon: <TaskAltIcon /> },
  { id: 'employees', label: 'Team Members', icon: <PeopleIcon /> },
];

function App() {
  const [activeTab, setActiveTab] = useState('projects');

  // Drill-down navigation state
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState(null);

  const isDrillDown = selectedProjectId || selectedEmployeeId || selectedConversationId || selectedSessionId;

  // Clear all drill-downs
  const clearDrillDown = () => {
    setSelectedProjectId(null);
    setSelectedEmployeeId(null);
    setSelectedConversationId(null);
    setSelectedSessionId(null);
  };

  // Navigation callbacks for child views to trigger drill-downs
  const navigateToProject = (projectId) => {
    clearDrillDown();
    setSelectedProjectId(projectId);
  };

  const navigateToEmployee = (employeeId) => {
    clearDrillDown();
    setSelectedEmployeeId(employeeId);
  };

  const navigateToConversation = (conversationId) => {
    clearDrillDown();
    setSelectedConversationId(conversationId);
  };

  const navigateToSession = (sessionId) => {
    clearDrillDown();
    setSelectedSessionId(sessionId);
  };

  // Back clears drill-down, returning to whatever tab is active
  const handleBack = () => {
    clearDrillDown();
  };

  // Clicking a tab clears any drill-down and switches tab
  const handleTabChange = (_, newValue) => {
    clearDrillDown();
    setActiveTab(newValue);
  };

  // Render the active drill-down view or the tab-based view
  const renderContent = () => {
    // Drill-down views take priority
    if (selectedSessionId) {
      return <ManagerChatView sessionId={selectedSessionId} onBack={handleBack} />;
    }
    if (selectedProjectId) {
      return <SprintBoardView projectId={selectedProjectId} onBack={handleBack} />;
    }
    if (selectedEmployeeId) {
      return <EmployeeDetailView employeeId={selectedEmployeeId} onBack={handleBack} />;
    }
    if (selectedConversationId) {
      return <ConversationView conversationId={selectedConversationId} onBack={handleBack} />;
    }

    // Tab views with navigation callbacks
    switch (activeTab) {
      case 'team-overview':
        return (
          <TeamOverviewView
            onProjectClick={navigateToProject}
            onEmployeeClick={navigateToEmployee}
            onConversationClick={navigateToConversation}
          />
        );
      case 'projects':
        return (
          <ProjectsView
            onProjectClick={navigateToProject}
            onEmployeeClick={navigateToEmployee}
          />
        );
      case 'tasks':
        return (
          <TasksView
            onProjectClick={navigateToProject}
            onEmployeeClick={navigateToEmployee}
          />
        );
      case 'employees':
        return (
          <EmployeesView
            onEmployeeClick={navigateToEmployee}
          />
        );
      default:
        return <ProjectsView onProjectClick={navigateToProject} onEmployeeClick={navigateToEmployee} />;
    }
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* Sidebar */}
      <Sidebar onSessionClick={navigateToSession} activeSessionId={selectedSessionId} />

      {/* Main content area */}
      <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0 }}>
        {/* App Header with inline tabs */}
        <AppBar
          position="static"
          elevation={0}
          sx={{ backgroundColor: 'background.paper', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
        >
          <Toolbar variant="dense" sx={{ gap: 1.5, minHeight: 48 }}>
            <RocketLaunchIcon sx={{ color: 'primary.main', fontSize: 22 }} />
            <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary', mr: 3, letterSpacing: 0.5 }}>
              Open <span style={{ color: '#4a90d9' }}>TEAM</span>
            </Typography>

            {/* Tabs always visible — clicking clears drill-down */}
            <Tabs
              value={isDrillDown ? false : activeTab}
              onChange={handleTabChange}
              variant="standard"
              sx={{
                flexGrow: 1,
                minHeight: 48,
                '& .MuiTab-root': {
                  textTransform: 'none',
                  fontWeight: 500,
                  minHeight: 48,
                  gap: 0.5,
                  fontSize: '0.85rem',
                  py: 0,
                  opacity: isDrillDown ? 0.5 : 1,
                },
                '& .MuiTabs-indicator': {
                  bottom: 0,
                  display: isDrillDown ? 'none' : 'block',
                },
              }}
            >
              {TABS.map(tab => (
                <Tab
                  key={tab.id}
                  value={tab.id}
                  label={tab.label}
                  icon={tab.icon}
                  iconPosition="start"
                />
              ))}
            </Tabs>

            <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>
              AI-Powered Team Dashboard
            </Typography>
          </Toolbar>
        </AppBar>

        {/* Scrollable view content */}
        <Box sx={{ flexGrow: 1, overflow: 'auto', p: 3 }}>
          {renderContent()}
        </Box>

        {/* Bottom Bar */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            px: 3,
            py: 1.5,
            borderTop: '1px solid rgba(255,255,255,0.06)',
            backgroundColor: 'background.paper',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer', '&:hover': { '& .MuiTypography-root': { color: 'text.primary' } } }}>
            <SettingsIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="caption" sx={{ color: 'text.secondary', transition: 'color 0.15s' }}>
              Settings
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer', '&:hover': { '& .MuiTypography-root': { color: 'text.primary' } } }}>
            <BugReportIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="caption" sx={{ color: 'text.secondary', transition: 'color 0.15s' }}>
              Debug Mode
            </Typography>
          </Box>
          <Box sx={{ flexGrow: 1 }} />
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            size="small"
            sx={{
              textTransform: 'none',
              borderColor: 'rgba(255, 255, 255, 0.15)',
              color: 'text.secondary',
              borderStyle: 'dashed',
              borderRadius: 2,
              fontSize: '0.8rem',
              '&:hover': {
                borderColor: 'primary.main',
                color: 'primary.light',
                backgroundColor: 'rgba(74, 144, 217, 0.08)',
                borderStyle: 'dashed',
              },
            }}
          >
            Add New AI-Powered Project!
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

export default App;
