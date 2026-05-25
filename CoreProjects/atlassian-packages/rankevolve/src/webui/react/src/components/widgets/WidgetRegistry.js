/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * WidgetRegistry — maps widget type strings to React components.
 */

import SingleChoiceWidget from './SingleChoiceWidget';
import MultipleChoiceWidget from './MultipleChoiceWidget';
import TextInputWidget from './TextInputWidget';
import ToggleWidget from './ToggleWidget';
import DropdownWidget from './DropdownWidget';
import ConfirmationWidget from './ConfirmationWidget';
import ToolArgumentFormWidget from './ToolArgumentFormWidget';
import MultiInputWidget from './MultiInputWidget';
import ProposalSelectionWidget from './ProposalSelectionWidget';
import GroupedWidget from './GroupedWidget';
import DefaultWidget from './DefaultWidget';

const WIDGET_REGISTRY = {
  'text_input': TextInputWidget,
  'free_text': TextInputWidget,  // InputMode.FREE_TEXT maps here
  'single_choice': SingleChoiceWidget,
  'multiple_choice': MultipleChoiceWidget,
  'multiple_choices': MultipleChoiceWidget,  // InputMode.MULTIPLE_CHOICE maps here
  'dropdown': DropdownWidget,
  'toggle': ToggleWidget,
  'confirmation': ConfirmationWidget,
  'tool_argument_form': ToolArgumentFormWidget,
  'multi_input': MultiInputWidget,  // Compound widget for multiple conversation tools (scalar tabs)
  'grouped': GroupedWidget,  // Plan v3 — rich-group widget (stacked rich widgets)
  'proposal_selection': ProposalSelectionWidget,  // Research proposal browser with phase tabs
  'default': DefaultWidget,
};

export function getWidget(type) {
  return WIDGET_REGISTRY[type] || WIDGET_REGISTRY['default'];
}

export default WIDGET_REGISTRY;
