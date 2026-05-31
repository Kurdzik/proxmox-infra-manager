"use client";

import { Box } from "@mantine/core";
import React from "react";
import { SidebarComponent } from "@/components/Sidebar";

export default function UILayout({ children }: { children: any }) {
  return (
    <Box
      style={{
        display: "flex",
        height: "100vh",
        overflow: "hidden",
        background: "var(--lnr-bg)",
      }}
    >
      <SidebarComponent />

      <Box
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          minWidth: 0,
        }}
      >
        <Box
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "24px",
          }}
        >
          {children}
        </Box>
      </Box>
    </Box>
  );
}
