/**
 * OpenStartup — AI Company Dashboard
 */

import React, { useState, useCallback, useRef } from 'react';
import Box from '@mui/material/Box';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Button from '@mui/material/Button';
import { useTheme } from '@mui/material/styles';
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
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState('projects');
  const [selectedProjectId, setSelectedProjectId] = useState(null);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState(null);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [selectedSessionId, setSelectedSessionId] = useState(null);

  const isDrillDown = selectedProjectId || selectedEmployeeId || selectedConversationId || selectedSessionId;

  const clearDrillDown = () => { setSelectedProjectId(null); setSelectedEmployeeId(null); setSelectedConversationId(null); setSelectedSessionId(null); };

  // Task bridge — tasks state is owned by useManagerChat inside ManagerChatView.
  // ManagerChatView calls onTasksChanged/onSwitchTabRef to keep App in sync for the Sidebar.
  const [sessionTasksMap, setSessionTasksMap] = useState({});
  const sessionTasks = sessionTasksMap[selectedSessionId] || {};
  const [activeTaskId, setActiveTaskId] = useState(null);
  const switchTabRef = useRef(null);

  const handleTasksChanged = useCallback((tasks) => {
    setSessionTasksMap(prev => ({ ...prev, [selectedSessionId]: tasks }));
  }, [selectedSessionId]);
  const handleActiveTaskChanged = useCallback((taskId) => setActiveTaskId(taskId), []);
  const handleSwitchTabRef = useCallback((fn) => { switchTabRef.current = fn; }, []);
  const handleSidebarTaskClick = useCallback((taskId) => {
    switchTabRef.current?.(taskId, 'task');
  }, []);
  const handleSidebarSessionClick = useCallback((sessionId) => {
    // Reset to session view first (clears task panel if open)
    switchTabRef.current?.(null, 'session');
    // Then navigate (clears drilldown state and sets the new session)
    setSelectedProjectId(null); setSelectedEmployeeId(null);
    setSelectedConversationId(null); setSelectedSessionId(sessionId);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const navigateToProject = (id) => { clearDrillDown(); setSelectedProjectId(id); };
  const navigateToEmployee = (id) => { clearDrillDown(); setSelectedEmployeeId(id); };
  const navigateToConversation = (id) => { clearDrillDown(); setSelectedConversationId(id); };
  const navigateToSession = (id) => { clearDrillDown(); setSelectedSessionId(id); };
  const handleBack = () => clearDrillDown();
  const handleTabChange = (_, newValue) => { clearDrillDown(); setActiveTab(newValue); };

  const renderContent = () => {
    if (selectedSessionId) return (
      <ManagerChatView
        key={selectedSessionId}
        sessionId={selectedSessionId}
        onBack={handleBack}
        onTasksChanged={handleTasksChanged}
        onActiveTaskChanged={handleActiveTaskChanged}
        onSwitchTabRef={handleSwitchTabRef}
      />
    );
    if (selectedProjectId) return <SprintBoardView projectId={selectedProjectId} onBack={handleBack} />;
    if (selectedEmployeeId) return <EmployeeDetailView employeeId={selectedEmployeeId} onBack={handleBack} />;
    if (selectedConversationId) return <ConversationView conversationId={selectedConversationId} onBack={handleBack} />;
    switch (activeTab) {
      case 'team-overview': return <TeamOverviewView onProjectClick={navigateToProject} onEmployeeClick={navigateToEmployee} onConversationClick={navigateToConversation} />;
      case 'projects': return <ProjectsView onProjectClick={navigateToProject} onEmployeeClick={navigateToEmployee} />;
      case 'tasks': return <TasksView onProjectClick={navigateToProject} onEmployeeClick={navigateToEmployee} />;
      case 'employees': return <EmployeesView onEmployeeClick={navigateToEmployee} />;
      default: return <ProjectsView onProjectClick={navigateToProject} onEmployeeClick={navigateToEmployee} />;
    }
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <Sidebar
        onSessionClick={handleSidebarSessionClick}
        activeSessionId={selectedSessionId}
        tasks={sessionTasks}
        activeTaskId={activeTaskId}
        onTaskClick={handleSidebarTaskClick}
      />
      <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, minWidth: 0 }}>
        <AppBar position="static" elevation={0} sx={{ backgroundColor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
          <Toolbar variant="dense" sx={{ gap: 1.5, minHeight: 48 }}>
            <RocketLaunchIcon sx={{ color: 'primary.main', fontSize: 22 }} />
            <Typography variant="h6" sx={{ fontWeight: 700, color: 'text.primary', mr: 3, letterSpacing: 0.5 }}>
              Open <Box component="span" sx={{ color: 'primary.main' }}>TEAM</Box>
            </Typography>
            <Tabs value={isDrillDown ? false : activeTab} onChange={handleTabChange} variant="standard" sx={{
              flexGrow: 1, minHeight: 48,
              '& .MuiTab-root': { textTransform: 'none', fontWeight: 500, minHeight: 48, gap: 0.5, fontSize: '0.85rem', py: 0, opacity: isDrillDown ? 0.5 : 1 },
              '& .MuiTabs-indicator': { bottom: 0, display: isDrillDown ? 'none' : 'block' },
            }}>
              {TABS.map(tab => <Tab key={tab.id} value={tab.id} label={tab.label} icon={tab.icon} iconPosition="start" />)}
            </Tabs>
            <Typography variant="caption" sx={{ color: 'text.secondary', whiteSpace: 'nowrap' }}>AI-Powered Team Dashboard</Typography>
          </Toolbar>
        </AppBar>

        <Box sx={{ flexGrow: 1, overflow: 'auto', p: 3 }}>{renderContent()}</Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, px: 3, py: 1.5, borderTop: '1px solid', borderColor: 'divider', backgroundColor: 'background.paper' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer', '&:hover': { '& .MuiTypography-root': { color: 'text.primary' } } }}>
            <SettingsIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="caption" sx={{ color: 'text.secondary', transition: 'color 0.15s' }}>Settings</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer', '&:hover': { '& .MuiTypography-root': { color: 'text.primary' } } }}>
            <BugReportIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="caption" sx={{ color: 'text.secondary', transition: 'color 0.15s' }}>Debug Mode</Typography>
          </Box>
          <Box sx={{ flexGrow: 1 }} />
          <Button variant="outlined" startIcon={<AddIcon />} size="small" sx={{
            textTransform: 'none', borderColor: theme.custom.surfaces.inputBorder, color: 'text.secondary', borderStyle: 'dashed', borderRadius: 2, fontSize: '0.8rem',
            '&:hover': { borderColor: 'primary.main', color: 'primary.light', backgroundColor: theme.custom.surfaces.highlightSubtle, borderStyle: 'dashed' },
          }}>
            Add New AI-Powered Project!
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

export default App;
