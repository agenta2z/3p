/**
 * usePromptViewer — manages state for the PromptViewerDrawer.
 *
 * Supports two modes:
 * - Prompt mode: shows template source, template feed variables, rendered prompt
 * - Full response mode: shows full raw response text
 */

import { useState, useCallback } from 'react';

export function usePromptViewer() {
  const [open, setOpen] = useState(false);
  const [promptData, setPromptData] = useState(null);
  const [fullResponseContent, setFullResponseContent] = useState(null);

  const openPrompt = useCallback((data) => {
    setPromptData(data);
    setFullResponseContent(null);
    setOpen(true);
  }, []);

  const openFullResponse = useCallback((content) => {
    setFullResponseContent(content);
    setPromptData(null);
    setOpen(true);
  }, []);

  const close = useCallback(() => {
    setOpen(false);
  }, []);

  return {
    open,
    promptData,
    fullResponseContent,
    openPrompt,
    openFullResponse,
    close,
  };
}

export default usePromptViewer;
