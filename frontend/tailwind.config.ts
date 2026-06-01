import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Pretendard Variable',
          'Pretendard',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Noto Sans KR',
          'Apple SD Gothic Neo',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        system: [
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'Segoe UI',
          'Roboto',
          'Noto Sans',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        playfair: [
          'Playfair Display',
          'ui-serif',
          'Georgia',
          'serif',
        ],
        // Display face for big numerals + Latin headings (Korean falls back to sans)
        display: [
          'Fraunces',
          'Pretendard Variable',
          'Pretendard',
          'ui-serif',
          'Georgia',
          'serif',
        ],
      },
      colors: {
        // Warm-clay design system (reference-matched)
        canvas: '#F7F4EF', // warm off-white app background
        surface: '#FFFFFF', // cards
        'surface-soft': '#F3EFE8', // subtle filled areas (nav hover, table head)
        ink: '#26211B', // primary warm near-black text
        'ink-soft': '#6B6258', // secondary text
        muted: '#9A9189', // tertiary / placeholder
        line: '#EBE5DB', // hairline borders
        'line-soft': '#F1ECE4',
        clay: {
          DEFAULT: '#BD5D3A', // primary accent (chart line, active marks)
          soft: '#D98E6F',
          wash: '#F6E7DE', // light fill / gradient stop
          ink: '#8C3F22', // accent text on light
        },
        positive: '#3E8E5A',
        negative: '#C0473B',
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
        '3xl': '1.5rem',
      },
      boxShadow: {
        card: '0 1px 2px rgba(38, 33, 27, 0.04), 0 8px 24px -12px rgba(38, 33, 27, 0.10)',
        'card-hover':
          '0 2px 4px rgba(38, 33, 27, 0.05), 0 16px 36px -16px rgba(38, 33, 27, 0.16)',
        pill: '0 1px 2px rgba(38, 33, 27, 0.06)',
      },
    },
  },
  plugins: [],
} satisfies Config;
