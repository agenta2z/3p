import React, { useState, useEffect, useMemo } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import ForumIcon from '@mui/icons-material/Forum';
import { useTheme, alpha } from '@mui/material/styles';
import { useApiData } from '../../../hooks/useApiData';
import ConversationThread from './shared/ConversationThread';

function relativeTime(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function getOtherParticipant(conversation, employeeId, allEmployees) {
  const otherId = (conversation.participant_ids || []).find((id) => id !== employeeId);
  if (!otherId) return { id: null, name: 'Unknown' };
  const emp = allEmployees.find((e) => e.id === otherId);
  return emp || { id: otherId, name: otherId };
}

export default function AIAIChatsDrilldown({ employeeId, allEmployees = [], periodData = {} }) {
  const theme = useTheme();
  const [selectedConversationId, setSelectedConversationId] = useState(null);

  // Fetch all conversations for this employee
  const { data: conversationsRaw, loading: loadingList } = useApiData(
    `/conversations?participant_id=${employeeId}`
  );

  // Filter to AI-AI only: all participants must be AI type
  const conversations = useMemo(() => {
    if (!conversationsRaw || !Array.isArray(conversationsRaw)) return [];
    return conversationsRaw
      .filter((conv) => {
        const pids = conv.participant_ids || [];
        return pids.every((pid) => {
          const emp = allEmployees.find((e) => e.id === pid);
          return emp && (emp.type === 'ai' || emp.type === 'agent');
        });
      })
      .sort((a, b) => new Date(b.last_message_at) - new Date(a.last_message_at));
  }, [conversationsRaw, allEmployees]);

  // Auto-select most recent conversation
  useEffect(() => {
    if (conversations.length > 0 && !selectedConversationId) {
      setSelectedConversationId(conversations[0].id);
    }
  }, [conversations, selectedConversationId]);

  // Fetch full conversation detail
  const { data: selectedConversation, loading: loadingDetail } = useApiData(
    selectedConversationId ? `/conversations/${selectedConversationId}` : null
  );

  const messages = selectedConversation?.messages || [];

  return (
    <Box sx={{ display: 'flex', height: '100%', minHeight: 0 }}>
      {/* ---- Left panel: Session sidebar ---- */}
      <Box
        sx={{
          width: '35%',
          minWidth: 0,
          borderRight: '1px solid',
          borderRightColor: 'divider',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Sidebar header */}
        <Box
          sx={{
            px: 1.5,
            py: 1,
            borderBottom: '1px solid',
            borderBottomColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            gap: 0.75,
            flexShrink: 0,
          }}
        >
          <ForumIcon sx={{ fontSize: 14, color: 'primary.light' }} />
          <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.72rem' }}>
            AI-AI Threads
          </Typography>
          <Chip
            label={conversations.length}
            size="small"
            sx={{
              height: 16,
              fontSize: '0.6rem',
              fontWeight: 700,
              ml: 'auto',
              backgroundColor: alpha(theme.palette.primary.main, 0.15),
              color: 'primary.light',
            }}
          />
        </Box>

        {/* Conversation list */}
        <Box sx={{ overflowY: 'auto', flex: 1, minHeight: 0 }}>
          {loadingList && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={20} />
            </Box>
          )}

          {!loadingList && conversations.length === 0 && (
            <Typography
              variant="caption"
              sx={{ color: 'text.secondary', textAlign: 'center', display: 'block', py: 3, fontSize: '0.72rem' }}
            >
              No AI-AI conversations found
            </Typography>
          )}

          {conversations.map((conv) => {
            const other = getOtherParticipant(conv, employeeId, allEmployees);
            const isSelected = conv.id === selectedConversationId;

            return (
              <Box
                key={conv.id}
                onClick={() => setSelectedConversationId(conv.id)}
                sx={{
                  px: 1.5,
                  py: 0.75,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 0.75,
                  backgroundColor: isSelected
                    ? alpha(theme.palette.primary.main, 0.1)
                    : 'transparent',
                  '&:hover': {
                    backgroundColor: isSelected
                      ? alpha(theme.palette.primary.main, 0.1)
                      : 'action.hover',
                  },
                  borderBottom: '1px solid',
                  borderBottomColor: alpha(theme.palette.divider, 0.4),
                  transition: 'background-color 0.15s',
                }}
              >
                <SmartToyIcon
                  sx={{
                    fontSize: 14,
                    color: isSelected ? 'primary.light' : 'text.secondary',
                    mt: 0.3,
                    flexShrink: 0,
                  }}
                />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Typography
                      variant="caption"
                      noWrap
                      sx={{
                        fontWeight: 600,
                        fontSize: '0.68rem',
                        color: isSelected ? 'primary.light' : 'text.primary',
                        flex: 1,
                        minWidth: 0,
                      }}
                    >
                      {other.name}
                    </Typography>
                    <Chip
                      label={conv.messages?.length || conv.message_count || 0}
                      size="small"
                      sx={{
                        height: 14,
                        fontSize: '0.55rem',
                        fontWeight: 600,
                        minWidth: 20,
                        backgroundColor: alpha(theme.palette.text.secondary, 0.12),
                      }}
                    />
                  </Box>
                  <Typography
                    variant="caption"
                    noWrap
                    sx={{ fontSize: '0.64rem', color: 'text.secondary', display: 'block', lineHeight: 1.3 }}
                  >
                    {conv.topic}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ fontSize: '0.58rem', color: 'text.disabled', lineHeight: 1.2 }}
                  >
                    {relativeTime(conv.last_message_at)}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Box>
      </Box>

      {/* ---- Right panel: Message thread ---- */}
      <Box
        sx={{
          width: '65%',
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Thread header */}
        {selectedConversation && (
          <Box
            sx={{
              px: 1.5,
              py: 0.75,
              borderBottom: '1px solid',
              borderBottomColor: 'divider',
              flexShrink: 0,
            }}
          >
            <Typography
              variant="caption"
              sx={{ fontWeight: 600, fontSize: '0.72rem', display: 'block', lineHeight: 1.3 }}
            >
              {selectedConversation.topic}
            </Typography>
            {selectedConversation.related_task_id && (
              <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
                Task: {selectedConversation.related_task_id}
              </Typography>
            )}
          </Box>
        )}

        {/* Thread content */}
        <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
          {loadingDetail && selectedConversationId && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress size={20} />
            </Box>
          )}

          {!selectedConversationId && conversations.length === 0 && !loadingList && (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
                No AI-AI conversations found
              </Typography>
            </Box>
          )}

          {selectedConversation && (
            <ConversationThread
              messages={messages}
              allEmployees={allEmployees}
              currentEmployeeId={employeeId}
              showReplyInput={false}
            />
          )}
        </Box>
      </Box>
    </Box>
  );
}
