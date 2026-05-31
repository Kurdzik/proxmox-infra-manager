"use client";
import { createTheme, rem } from "@mantine/core";

export const theme = createTheme({
  defaultRadius: "4px",
  cursorType: "pointer",

  fontFamily: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif`,

  fontSizes: {
    xs: rem(11),
    sm: rem(12),
    md: rem(13),
    lg: rem(14),
    xl: rem(16),
  },

  lineHeights: {
    xs: "1.4",
    sm: "1.4",
    md: "1.4",
    lg: "1.4",
    xl: "1.4",
  },

  spacing: {
    xs: rem(4),
    sm: rem(8),
    md: rem(16),
    lg: rem(24),
    xl: rem(40),
  },

  colors: {
    accent: [
      "#eef0fc",
      "#d5d9f7",
      "#b3baef",
      "#8f99e7",
      "#7280de",
      "#5e6ad2",
      "#5460c4",
      "#4a55b5",
      "#3d4796",
      "#303878",
    ],
    dark: [
      "#e1e1e3",
      "#8f8f9e",
      "#5a5a6e",
      "#2e2e33",
      "#252528",
      "#1c1c20",
      "#16161a",
      "#111113",
      "#0d0d10",
      "#080809",
    ],
    success: [
      "#f0fdf4", "#dcfce7", "#bbf7d0", "#86efac", "#4ade80",
      "#4caf50", "#3d9b42", "#2d8a34", "#1e6b25", "#0f4c17",
    ],
    warning: [
      "#fffbeb", "#fef3c7", "#fde68a", "#fcd34d", "#fbbf24",
      "#f59e0b", "#d97706", "#b45309", "#92400e", "#78350f",
    ],
    error: [
      "#fef2f2", "#fee2e2", "#fecaca", "#fca5a5", "#f87171",
      "#ef4444", "#dc2626", "#b91c1c", "#991b1b", "#7f1d1d",
    ],
  },

  primaryColor: "accent",
  primaryShade: 5,

  shadows: {
    xs: "0 1px 2px 0 rgba(0,0,0,0.3)",
    sm: "0 1px 4px 0 rgba(0,0,0,0.4)",
    md: "0 4px 12px rgba(0,0,0,0.5)",
    lg: "0 8px 24px rgba(0,0,0,0.5)",
    xl: "0 16px 40px rgba(0,0,0,0.6)",
  },

  headings: {
    fontFamily: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`,
    fontWeight: "600",
    sizes: {
      h1: { fontSize: rem(24), lineHeight: "1.3", fontWeight: "600" },
      h2: { fontSize: rem(20), lineHeight: "1.35", fontWeight: "600" },
      h3: { fontSize: rem(16), lineHeight: "1.4", fontWeight: "600" },
      h4: { fontSize: rem(14), lineHeight: "1.4", fontWeight: "500" },
      h5: { fontSize: rem(13), lineHeight: "1.4", fontWeight: "500" },
      h6: { fontSize: rem(12), lineHeight: "1.45", fontWeight: "500" },
    },
  },

  components: {
    Button: {
      defaultProps: { size: "sm" },
      styles: {
        root: {
          fontWeight: 500,
          fontSize: rem(13),
          transition: "var(--lnr-transition)",
          borderRadius: "4px",
        },
      },
    },
    Paper: {
      defaultProps: { shadow: "none", radius: "4px" },
      styles: {
        root: {
          backgroundColor: "var(--lnr-surface)",
          border: "1px solid var(--lnr-border)",
          borderRadius: "4px",
        },
      },
    },
    Modal: {
      defaultProps: { radius: "6px", size: "md" },
      styles: {
        content: {
          backgroundColor: "var(--lnr-elevated)",
          border: "1px solid var(--lnr-border-strong)",
          borderRadius: "6px",
        },
        header: {
          backgroundColor: "var(--lnr-elevated)",
          paddingBottom: rem(16),
          marginBottom: rem(4),
          borderBottom: "1px solid var(--lnr-border)",
        },
        title: { fontWeight: 600, fontSize: rem(14), color: "var(--lnr-text)" },
        body: { padding: rem(24) },
      },
    },
    Input: {
      styles: {
        input: {
          backgroundColor: "var(--lnr-surface)",
          border: "1px solid var(--lnr-border-strong)",
          borderRadius: "4px",
          fontSize: rem(13),
          color: "var(--lnr-text)",
        },
        label: {
          fontSize: rem(12),
          fontWeight: 500,
          color: "var(--lnr-text-muted)",
          marginBottom: rem(4),
        },
      },
    },
    Select: {
      styles: {
        input: { borderRadius: "4px", fontSize: rem(13) },
        dropdown: {
          backgroundColor: "var(--lnr-elevated)",
          border: "1px solid var(--lnr-border-strong)",
          borderRadius: "4px",
        },
        option: {
          fontSize: rem(13),
          borderRadius: "3px",
          "&[data-selected]": {
            backgroundColor: "var(--lnr-accent-muted)",
            color: "var(--lnr-accent)",
          },
        },
      },
    },
    Table: {
      styles: {
        table: { fontSize: rem(13) },
        thead: { borderBottom: "1px solid var(--lnr-border)" },
        th: {
          fontSize: rem(11),
          fontWeight: 500,
          color: "var(--lnr-text-faint)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          padding: `${rem(8)} ${rem(12)}`,
          borderBottom: "none",
        },
        td: {
          padding: `${rem(8)} ${rem(12)}`,
          color: "var(--lnr-text)",
          borderBottom: "1px solid var(--lnr-border)",
        },
        tr: { "&:hover": { backgroundColor: "rgba(255,255,255,0.02)" } },
      },
    },
    Badge: {
      styles: {
        root: {
          fontWeight: 500,
          fontSize: rem(11),
          borderRadius: "999px",
          textTransform: "none",
          letterSpacing: 0,
        },
      },
    },
    Tooltip: {
      defaultProps: { withArrow: false },
      styles: {
        tooltip: {
          backgroundColor: "var(--lnr-elevated)",
          border: "1px solid var(--lnr-border-strong)",
          color: "var(--lnr-text)",
          fontSize: rem(12),
          borderRadius: "4px",
          padding: `${rem(4)} ${rem(8)}`,
        },
      },
    },
    Divider: {
      styles: { root: { borderColor: "var(--lnr-border)" } },
    },
  },
});
