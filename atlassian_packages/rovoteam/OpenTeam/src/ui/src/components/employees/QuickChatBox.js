import React, { useState, useRef, useEffect } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import CloseIcon from '@mui/icons-material/Close';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SendIcon from '@mui/icons-material/Send';

const CANNED_RESPONSES = [
  "I'm currently working on this. Let me check and get back to you with details.",
  "Good question. Based on my current task progress, I'd estimate completion by end of day.",
  "I'll look into that right away. Is there anything specific you'd like me to prioritize?",
  "Understood. I'll update the task status and notify you when it's done.",
  "That's a great point. I'll factor that into my approach going forward.",
];

export default function QuickChatBox({ agentName, onClose, onFormalize }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [promoted, setPromoted] = useState(false);
  const responseIdx = useRef(0);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;

    const userMsg = { sender: 'manager', text, ts: Date.now() };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setInput('');

    setTimeout(() => {
      const reply = CANNED_RESPONSES[responseIdx.current % CANNED_RESPONSES.length];
      responseIdx.current += 1;
      setMessages((prev) => [...prev, { sender: 'agent', text: reply, ts: Date.now() }]);
    }, 800);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFormalize = () => {
    setPromoted(true);
    setTimeout(() => {
      if (onFormalize) onFormalize(messages);
    }, 800);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          px: 1.5,
          py: 0.75,
          borderBottom: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
          Quick Chat with {agentName}
        </Typography>
        <IconButton size="small" onClick={onClose} sx={{ p: 0.25 }}>
          <CloseIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
        </IconButton>
      </Box>

      {/* Messages */}
      <Box
        sx={{
          maxHeight: 350,
          overflowY: 'auto',
          px: 1.5,
          py: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
        }}
      >
        {messages.length === 0 && (
          <Typography variant="caption" sx={{ color: 'text.secondary', textAlign: 'center', py: 2, fontSize: '0.75rem' }}>
            Start a quick conversation with {agentName}
          </Typography>
        )}
        {messages.map((msg, idx) => {
          const isManager = msg.sender === 'manager';
          return (
            <Box
              key={idx}
              sx={{
                display: 'flex',
                justifyContent: isManager ? 'flex-end' : 'flex-start',
                gap: 0.5,
              }}
            >
              {!isManager && (
                <SmartToyIcon sx={{ fontSize: 14, color: 'text.secondary', mt: 0.25, flexShrink: 0 }} />
              )}
              <Box
                sx={{
                  maxWidth: '80%',
                  px: 1,
                  py: 0.5,
                  borderRadius: 1.5,
                  backgroundColor: isManager ? 'rgba(74,144,217,0.25)' : 'rgba(255,255,255,0.06)',
                }}
              >
                {!isManager && (
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem', display: 'block', lineHeight: 1.2 }}>
                    {agentName}
                  </Typography>
                )}
                <Typography variant="body2" sx={{ fontSize: '0.8rem', lineHeight: 1.4 }}>
                  {msg.text}
                </Typography>
              </Box>
            </Box>
          );
        })}
        <div ref={messagesEndRef} />
      </Box>

      {/* Input */}
      <Box
        sx={{
          display: 'flex',
          gap: 0.5,
          px: 1.5,
          py: 0.75,
          borderTop: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <TextField
          size="small"
          fullWidth
          placeholder="Type a message..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          sx={{
            '& .MuiInputBase-root': {
              fontSize: '0.8rem',
              height: 30,
            },
          }}
        />
        <IconButton size="small" onClick={handleSend} disabled={!input.trim()} sx={{ color: 'primary.light' }}>
          <SendIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Box>

      {/* Formalize button */}
      <Box sx={{ px: 1.5, py: 0.75, borderTop: '1px solid rgba(255,255,255,0.06)', textAlign: 'center' }}>
        {promoted ? (
          <Typography variant="caption" sx={{ color: 'success.main', fontWeight: 600, fontSize: '0.75rem' }}>
            Promoted!
          </Typography>
        ) : (
          <Button
            size="small"
            onClick={handleFormalize}
            disabled={messages.length === 0}
            sx={{
              textTransform: 'none',
              fontSize: '0.7rem',
              color: 'text.secondary',
              '&:hover': { backgroundColor: 'rgba(255,255,255,0.06)' },
            }}
          >
            Make this a formal conversation
          </Button>
        )}
      </Box>
    </Box>
  );
}
