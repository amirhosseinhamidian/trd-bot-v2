import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { CHART_SERIES_COLORS } from '@/components/charts/chart-colors';

const globalsCss = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8');
const localeLayout = readFileSync(resolve(process.cwd(), 'src/app/[locale]/layout.tsx'), 'utf8');

function extractBlock(pattern: RegExp, label: string): string {
  const match = globalsCss.match(pattern);

  if (!match) {
    throw new Error(`Missing ${label} token block`);
  }

  return match[1];
}

function expectDeclarations(block: string, declarations: Record<string, string>): void {
  for (const [token, value] of Object.entries(declarations)) {
    expect(block).toContain(`--app-${token}: ${value};`);
  }
}

function readHexToken(block: string, token: string): string {
  const match = block.match(new RegExp(`--app-${token}:\\s*(#[0-9a-f]{6});`, 'i'));

  if (!match) {
    throw new Error(`Missing hexadecimal --app-${token} token`);
  }

  return match[1];
}

function relativeLuminance(hex: string): number {
  const channels = hex
    .slice(1)
    .match(/.{2}/g)
    ?.map((channel) => Number.parseInt(channel, 16) / 255)
    .map((channel) => (channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4));

  if (!channels || channels.length !== 3) {
    throw new Error(`Invalid hexadecimal color: ${hex}`);
  }

  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function contrastRatio(first: string, second: string): number {
  const firstLuminance = relativeLuminance(first);
  const secondLuminance = relativeLuminance(second);
  const lighter = Math.max(firstLuminance, secondLuminance);
  const darker = Math.min(firstLuminance, secondLuminance);

  return (lighter + 0.05) / (darker + 0.05);
}

const darkTheme = extractBlock(/:root\s*\{([\s\S]*?)\n\}/, 'dark theme');
const lightTheme = extractBlock(/:root\[data-theme='light'\]\s*\{([\s\S]*?)\n\}/, 'light theme');
const tailwindTheme = extractBlock(/@theme inline\s*\{([\s\S]*?)\n\}/, 'Tailwind theme');

const semanticColorTokens = [
  'accent-hover',
  'control-border',
  'success',
  'success-soft',
  'success-border',
  'danger',
  'danger-soft',
  'danger-border',
  'warning',
  'warning-soft',
  'warning-border',
  'info',
  'info-soft',
  'info-border',
  'chart-1',
  'chart-2',
  'chart-3',
  'chart-4',
  'chart-5',
  'chart-6',
] as const;

describe('Nexora design token contract', () => {
  it('keeps the 320px viewport and locale direction contracts explicit', () => {
    expect(globalsCss).toMatch(/html\s*\{[\s\S]*?min-width:\s*320px;/);
    expect(localeLayout).toContain('lang={locale}');
    expect(localeLayout).toContain("dir={locale === 'fa' ? 'rtl' : 'ltr'}");
  });

  it('reduces animations, transitions, and smooth scrolling at the user preference level', () => {
    expect(globalsCss).toContain('@media (prefers-reduced-motion: reduce)');
    expect(globalsCss).toContain('*::before');
    expect(globalsCss).toContain('*::after');
    expect(globalsCss).toContain('scroll-behavior: auto !important;');
    expect(globalsCss).toContain('animation-duration: 1ms !important;');
    expect(globalsCss).toContain('animation-iteration-count: 1 !important;');
    expect(globalsCss).toContain('transition-duration: 1ms !important;');
    expect(globalsCss).toMatch(
      /\.app-select-content\[data-state\]\s*\{[\s\S]*?animation:\s*none !important;/,
    );
  });

  it('uses app-scoped Select animation identifiers', () => {
    expect(globalsCss).toContain('@keyframes app-select-open');
    expect(globalsCss).toContain('@keyframes app-select-close');
    expect(globalsCss).toContain(".app-select-content[data-state='open']");
    expect(globalsCss).not.toContain('trd-select');
  });

  it('exports every semantic status and chart token to Tailwind', () => {
    for (const token of semanticColorTokens) {
      expect(tailwindTheme).toContain(`--color-app-${token}: var(--app-${token});`);
    }
  });

  it('provides a theme-aware elevated-surface shadow', () => {
    expect(tailwindTheme).toContain('--shadow-app-surface: 0 16px 36px var(--app-shadow-color);');
    expect(darkTheme).toContain('--app-shadow-color: rgba(0, 0, 0, 0.28);');
    expect(lightTheme).toContain('--app-shadow-color: rgba(10, 26, 47, 0.12);');
  });

  it('keeps the frozen dark palette and complete semantic coverage', () => {
    expectDeclarations(darkTheme, {
      background: '#020817',
      surface: '#08162a',
      'surface-muted': '#0e2038',
      border: '#244666',
      'control-border': '#3c678f',
      foreground: '#f2f8ff',
      muted: '#a3b6cc',
      subtle: '#7c91aa',
      accent: '#22d3ee',
      'accent-hover': '#67e8f9',
      success: '#34d399',
      danger: '#fb7185',
      warning: '#fbbf24',
      info: '#38bdf8',
      'chart-1': '#22d3ee',
      'chart-2': '#3b82f6',
      'chart-3': '#2dd4bf',
      'chart-4': '#a78bfa',
      'chart-5': '#fbbf24',
      'chart-6': '#fb7185',
    });

    for (const token of semanticColorTokens) {
      expect(darkTheme).toContain(`--app-${token}:`);
    }
  });

  it('keeps the frozen light palette and complete semantic coverage', () => {
    expectDeclarations(lightTheme, {
      background: '#f5f9fc',
      surface: '#ffffff',
      'surface-muted': '#e4eef6',
      border: '#b8cce0',
      'control-border': '#7795b2',
      foreground: '#0a1a2f',
      muted: '#455d76',
      subtle: '#526a82',
      accent: '#0e7490',
      'accent-hover': '#155e75',
      success: '#047857',
      danger: '#be123c',
      warning: '#b45309',
      info: '#0369a1',
      'chart-1': '#0891b2',
      'chart-2': '#2563eb',
      'chart-3': '#0f766e',
      'chart-4': '#7c3aed',
      'chart-5': '#d97706',
      'chart-6': '#e11d48',
    });

    for (const token of semanticColorTokens) {
      expect(lightTheme).toContain(`--app-${token}:`);
    }
  });

  it('provides stable chart-series references for SVG consumers', () => {
    expect(CHART_SERIES_COLORS).toEqual({
      cyan: 'var(--app-chart-1)',
      blue: 'var(--app-chart-2)',
      teal: 'var(--app-chart-3)',
      violet: 'var(--app-chart-4)',
      amber: 'var(--app-chart-5)',
      rose: 'var(--app-chart-6)',
    });
  });

  it('keeps primary text and status foregrounds at WCAG AA contrast', () => {
    const cases = [
      { block: darkTheme, background: 'background', foreground: 'foreground' },
      { block: darkTheme, background: 'background', foreground: 'muted' },
      { block: darkTheme, background: 'background', foreground: 'subtle' },
      { block: darkTheme, background: 'background', foreground: 'accent' },
      { block: lightTheme, background: 'background', foreground: 'foreground' },
      { block: lightTheme, background: 'background', foreground: 'muted' },
      { block: lightTheme, background: 'background', foreground: 'subtle' },
      { block: lightTheme, background: 'background', foreground: 'accent' },
      ...(['success', 'danger', 'warning', 'info'] as const).flatMap((foreground) => [
        { block: darkTheme, background: 'surface', foreground },
        { block: lightTheme, background: 'surface', foreground },
      ]),
    ];

    for (const { background, block, foreground } of cases) {
      const ratio = contrastRatio(readHexToken(block, foreground), readHexToken(block, background));

      expect(ratio, `${foreground} on ${background}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('keeps interactive boundaries and primary actions distinguishable in both themes', () => {
    for (const block of [darkTheme, lightTheme]) {
      expect(
        contrastRatio(readHexToken(block, 'control-border'), readHexToken(block, 'surface')),
        'control border on surface',
      ).toBeGreaterThanOrEqual(3);

      for (const background of ['accent', 'accent-hover']) {
        expect(
          contrastRatio(readHexToken(block, 'background'), readHexToken(block, background)),
          `background text on ${background}`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
