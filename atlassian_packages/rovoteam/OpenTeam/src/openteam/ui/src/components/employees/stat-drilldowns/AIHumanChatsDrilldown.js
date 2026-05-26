import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Avatar from '@mui/material/Avatar';
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
  if (!otherId) return { id: null, name: 'Unknown', type: 'unknown', role: '' };
  const emp = allEmployees.find((e) => e.id === otherId);
  return emp || { id: otherId, name: otherId, type: 'unknown', role: '' };
}

export default function AIHumanChatsDrilldown({ employeeId, allEmployees = [], periodData = {} }) {
  const theme = useTheme();
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [localMessages, setLocalMessages] = useState([]);
  const [localMsgIdCounter, setLocalMsgIdCounter] = useState(1);

  // Fetch all conversations for this employee
  const { data: conversationsRaw, loading: loadingList } = useApiData(
    `/conversations?participant_id=${employeeId}`
  );

  // Filter to AI-Human: at least one participant is human AND employeeId is a participant
  const conversations = useMemo(() => {
    if (!conversationsRaw || !Array.isArray(conversationsRaw)) return [];
    return conversationsRaw
      .filter((conv) => {
        const pids = conv.participant_ids || [];
        if (!pids.includes(employeeId)) return false;
        return pids.some((pid) => {
          const emp = allEmployees.find((e) => e.id === pid);
          return emp && emp.type === 'human';
        });
      })
      .sort((a, b) => new Date(b.last_message_at) - new Date(a.last_message_at));
  }, [conversationsRaw, allEmployees, employeeId]);

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

  // Reset local messages when conversation changes
  useEffect(() => {
    if (selectedConversation?.messages) {
      setLocalMessages(selectedConversation.messages);
      setLocalMsgIdCounter(1);
    }
  }, [selectedConversation]);

  // Find the AI participant in the current conversation for simulated responses
  const aiParticipant = useMemo(() => {
    if (!selectedConversation) return null;
    const pids = selectedConversation.participant_ids || [];
    for (const pid of pids) {
      const emp = allEmployees.find((e) => e.id === pid);
      if (emp && (emp.type === 'ai' || emp.type === 'agent')) return emp;
    }
    return null;
  }, [selectedConversation, allEmployees]);

  const handleSendMessage = useCallback(
    (text) => {
      // Determine if this is a user-sent message or a simulated AI reply.
      // The ConversationThread component calls onSendMessage for both the
      // user's text and (after 1.5s) a canned AI reply. We distinguish
      // by checking if the text matches a canned response pattern.
      // Instead, we handle both cases: the first call is the user message,
      // and the component handles the simulated reply internally.

      // Because ConversationThread calls onSendMessage for BOTH the user
      // message and the simulated reply, we append each as appropriate.
      const isSimulatedReply = text.includes('[Simulated response]') ||
        text.startsWith("Got it.") ||
        text.startsWith("Thanks for the context") ||
        text.startsWith("Acknowledged.") ||
        text.startsWith("Understood.") ||
        text.startsWith("Good point.");

      const newMsg = {
        id: `local-msg-${Date.now()}-${localMsgIdCounter}`,
        sender_id: isSimulatedReply ? (aiParticipant?.id || employeeId) : employeeId,
        sender_name: isSimulatedReply ? (aiParticipant?.name || 'AI Assistant') : (
          allEmployees.find((e) => e.id === employeeId)?.name || 'You'
        ),
        timestamp: new Date().toISOString(),
        content: text,
        mentions: [],
      };

      setLocalMsgIdCounter((c) => c + 1);
      setLocalMessages((prev) => [...prev, newMsg]);
    },
    [employeeId, aiParticipant, allEmployees, localMsgIdCounter]
  );

  // Build participant info string for header
  const participantInfo = useMemo(() => {
    if (!selectedConversation) return '';
    return (selectedConversation.participant_ids || [])
      .map((pid) => {
        const emp = allEmployees.find((e) => e.id === pid);
        return emp ? emp.name : pid;
      })
      .join(' & ');
  }, [selectedConversation, allEmployees]);

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
          <ForumIcon sx={{ fontSize: 14, color: 'secondary.light' }} />
          <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.72rem' }}>
            AI-Human Threads
          </Typography>
          <Chip
            label={conversations.length}
            size="small"
            sx={{
              height: 16,
              fontSize: '0.6rem',
              fontWeight: 700,
              ml: 'auto',
              backgroundColor: alpha(theme.palette.secondary.main, 0.15),
              color: 'secondary.light',
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
              No AI-Human conversations found
            </Typography>
          )}

          {conversations.map((conv) => {
            const other = getOtherParticipant(conv, employeeId, allEmployees);
            const isSelected = conv.id === selectedConversationId;
            const isHuman = other.type === 'human';

            return (
              <Box
                key={conv.id}
                onClick={() => {
                  setSelectedConversationId(conv.id);
                }}
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
                {isHuman ? (
                  <Avatar
                    sx={{
                      width: 18,
                      height: 18,
                      fontSize: '0.55rem',
                      fontWeight: 700,
                      mt: 0.3,
                      flexShrink: 0,
                      bgcolor: alpha(theme.palette.secondary.main, 0.3),
                      color: 'secondary.light',
                    }}
                  >
                    {(other.name || '?')[0].toUpperCase()}
                  </Avatar>
                ) : (
                  <SmartToyIcon
                    sx={{
                      fontSize: 14,
                      color: isSelected ? 'primary.light' : 'text.secondary',
                      mt: 0.3,
                      flexShrink: 0,
                    }}
                  />
                )}
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
                  {isHuman && other.role && (
                    <Typography
                      variant="caption"
                      noWrap
                      sx={{ fontSize: '0.6rem', color: 'text.disabled', display: 'block', lineHeight: 1.2 }}
                    >
                      {other.role}
                    </Typography>
                  )}
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
            <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.secondary' }}>
              {participantInfo}
            </Typography>
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
                No AI-Human conversations found
              </Typography>
            </Box>
          )}

          {selectedConversation && (
            <ConversationThread
              messages={localMessages}
              allEmployees={allEmployees}
              currentEmployeeId={employeeId}
              showReplyInput={true}
              onSendMessage={handleSendMessage}
            />
          )}
        </Box>
      </Box>
    </Box>
  );
}
