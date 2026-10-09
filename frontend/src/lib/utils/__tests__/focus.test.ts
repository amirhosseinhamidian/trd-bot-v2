import { afterEach, describe, expect, it } from 'vitest';

import { getFocusableElements, trapTabFocus } from '@/lib/utils/focus';

function createTabEvent(shiftKey = false): KeyboardEvent {
  return new KeyboardEvent('keydown', {
    bubbles: true,
    cancelable: true,
    key: 'Tab',
    shiftKey,
  });
}

afterEach(() => {
  document.body.replaceChildren();
});

describe('focus utilities', () => {
  it('keeps only available controls in document order', () => {
    const container = document.createElement('div');

    container.innerHTML = `
      <a href="#first">First</a>
      <input type="hidden" value="ignored" />
      <div hidden><button>Hidden</button></div>
      <div inert><button>Inert</button></div>
      <button aria-disabled="true">ARIA disabled</button>
      <button disabled>Disabled</button>
      <button>Last</button>
    `;
    document.body.append(container);

    expect(getFocusableElements(container).map((element) => element.textContent?.trim())).toEqual([
      'First',
      'Last',
    ]);
  });

  it('wraps focus in both keyboard directions', () => {
    const container = document.createElement('div');

    container.innerHTML = '<button>First</button><button>Last</button>';
    document.body.append(container);

    const [first, last] = getFocusableElements(container);

    last?.focus();
    const forwardEvent = createTabEvent();
    trapTabFocus(forwardEvent, container);

    expect(forwardEvent.defaultPrevented).toBe(true);
    expect(first).toHaveFocus();

    const backwardEvent = createTabEvent(true);
    trapTabFocus(backwardEvent, container);

    expect(backwardEvent.defaultPrevented).toBe(true);
    expect(last).toHaveFocus();
  });

  it('focuses an empty trap container as a safe fallback', () => {
    const container = document.createElement('section');

    document.body.append(container);

    const event = createTabEvent();
    trapTabFocus(event, container);

    expect(event.defaultPrevented).toBe(true);
    expect(container).toHaveAttribute('tabindex', '-1');
    expect(container).toHaveFocus();
  });
});
