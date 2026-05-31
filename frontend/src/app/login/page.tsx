"use client";

import { useState } from "react";
import {
  Title,
  Text,
  Button,
  TextInput,
  PasswordInput,
  Stack,
  Paper,
  Box,
  rem,
  Flex,
  Group,
} from "@mantine/core";
import { IconUser, IconLock, IconLogin, IconServerBolt, IconArrowRight } from "@tabler/icons-react";
import { post } from "@/lib/backendRequests";
import { setAuthCookie } from "@/lib/cookies";
import { ApiResponse } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

interface NotificationState {
  message: string;
  statusCode: number;
}

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<NotificationState | null>(null);

  const isFormValid = () => !!(username && password);

  const handleLogin = async () => {
    if (!isFormValid()) return;
    try {
      setLoading(true);
      setNotification(null);
      const response: ApiResponse<{ token: string }> = await post(
        "users/login",
        { username, password },
        false,
      );
      if (response.status === 200 && response.data?.token) {
        setAuthCookie(response.data.token);
        setNotification({ message: "Login successful", statusCode: 200 });
        setTimeout(() => {
          window.location.href = "/ui/dashboard";
        }, 1000);
      } else {
        setNotification({ message: response.detail || "Login failed", statusCode: response.status || 400 });
      }
    } catch (err: any) {
      setNotification({ message: err.message || "An error occurred", statusCode: 500 });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && isFormValid()) handleLogin();
  };

  return (
    <Flex justify="center" align="center" style={{ minHeight: "100vh", width: "100%" }}>
      <Paper
        shadow="md"
        p="xl"
        radius={0}
        withBorder
        style={{
          width: "100%",
          maxWidth: rem(400),
          backgroundColor: "var(--lnr-surface)",
          border: "1px solid var(--lnr-border)",
        }}
      >
        <Stack gap="lg">
          <Box ta="center" mb="md">
            <Flex justify="center" mb="md">
              <Box
                style={{
                  padding: rem(12),
                  borderRadius: 4,
                  backgroundColor: "var(--lnr-accent-muted)",
                  border: "1px solid var(--lnr-border)",
                }}
              >
                <IconServerBolt size={24} color="var(--lnr-accent)" stroke={1.5} />
              </Box>
            </Flex>
            <Title order={2} size="1.5rem" fw={600} mb="xs" style={{ color: "var(--lnr-text)" }}>
              Infra Manager
            </Title>
            <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
              Sign in to manage your infrastructure
            </Text>
          </Box>

          {notification && (
            <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
          )}

          <Stack gap="md">
            <TextInput
              label="Username"
              placeholder="Enter your username"
              required
              size="sm"
              leftSection={<IconUser size={16} color="var(--lnr-text-faint)" />}
              value={username}
              onChange={(e) => setUsername(e.currentTarget.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
            <PasswordInput
              label="Password"
              placeholder="Enter your password"
              required
              size="sm"
              leftSection={<IconLock size={16} color="var(--lnr-text-faint)" />}
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
            />
            <Button
              fullWidth
              size="sm"
              rightSection={<IconLogin size={16} />}
              onClick={handleLogin}
              loading={loading}
              disabled={!isFormValid() || loading}
              mt="md"
            >
              Sign In
            </Button>
          </Stack>

          <Box pt="md" style={{ borderTop: "1px solid var(--lnr-border)" }}>
            <Group justify="center" gap="xs">
              <Text size="sm" c="dimmed">
                Don&apos;t have an account?
              </Text>
              <Button
                variant="subtle"
                size="xs"
                rightSection={<IconArrowRight size={14} />}
                onClick={() => { window.location.href = "/register"; }}
                disabled={loading}
                styles={{ root: { color: "var(--lnr-accent)", fontSize: rem(13), fontWeight: 500, padding: "0 4px", border: 0, height: rem(24) } }}
              >
                Create Account
              </Button>
            </Group>
          </Box>
        </Stack>
      </Paper>
    </Flex>
  );
}
