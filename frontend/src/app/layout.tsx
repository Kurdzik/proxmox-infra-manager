"use client";

import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";
import "./globals.css";
import { ColorSchemeScript, MantineProvider } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { Inter } from "next/font/google";
import React from "react";
import { theme } from "../../theme";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export default function RootLayout({ children }: { children: any }) {
  return (
    <html lang="en" className={inter.className}>
      <head>
        <title>Infra Manager</title>
        <ColorSchemeScript defaultColorScheme="dark" />
        <meta
          name="viewport"
          content="minimum-scale=1, initial-scale=1, width=device-width, user-scalable=no"
        />
      </head>
      <body>
        <MantineProvider theme={theme} defaultColorScheme="dark">
          <Notifications position="bottom-center" />
          {children}
        </MantineProvider>
      </body>
    </html>
  );
}
