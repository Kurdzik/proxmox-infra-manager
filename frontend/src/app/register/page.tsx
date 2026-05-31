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
import { IconUser, IconLock, IconUserPlus, IconServerBolt, IconArrowRight } from "@tabler/icons-react";
import { post } from "@/lib/backendRequests";
import { setAuthCookie } from "@/lib/cookies";
import { ApiResponse } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

interface NotificationState {
  message: string;
  statusCode: number;
}

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState<NotificationState | null>(null);

  const isFormValid = () => !!(username && password && password === password2 && password.length >= 8);

  const handleRegister = async () => {
    if (!isFormValid()) return;
    try {
      setLoading(true);
      setNotification(null);
      const response: ApiResponse<{ session_token: string }> = await post(
        "users/register",
        { username, password },
        false,
      );
      if (response.status === 200 && response.data?.session_token) {
        setAuthCookie(response.data.session_token);
        setNotification({ message: "Account created successfully", statusCode: 200 });
        setTimeout(() => {
          window.location.href = "/ui/dashboard";
        }, 1000);
      } else {
        setNotification({ message: response.detail || "Registration failed", statusCode: response.status || 400 });
      }
    } catch (err: any) {
      setNotification({ message: err.message || "An error occurred", statusCode: 500 });
    } finally {
      setLoading(false);
    }
  };

  const passwordMismatch = password2 && password !== password2;

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
              Create Account
            </Title>
            <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
              The first registered user becomes the platform admin
            </Text>
          </Box>

          {notification && (
            <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
          )}

          <Stack gap="md">
            <TextInput
              label="Username"
              placeholder="Choose a username"
              required
              size="sm"
              leftSection={<IconUser size={16} color="var(--lnr-text-faint)" />}
              value={username}
              onChange={(e) => setUsername(e.currentTarget.value)}
              disabled={loading}
            />
            <PasswordInput
              label="Password"
              placeholder="Minimum 8 characters"
              required
              size="sm"
              leftSection={<IconLock size={16} color="var(--lnr-text-faint)" />}
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              disabled={loading}
              error={password && password.length < 8 ? "Password must be at least 8 characters" : undefined}
            />
            <PasswordInput
              label="Confirm Password"
              placeholder="Repeat your password"
              required
              size="sm"
              leftSection={<IconLock size={16} color="var(--lnr-text-faint)" />}
              value={password2}
              onChange={(e) => setPassword2(e.currentTarget.value)}
              disabled={loading}
              error={passwordMismatch ? "Passwords do not match" : undefined}
            />
            <Button
              fullWidth
              size="sm"
              rightSection={<IconUserPlus size={16} />}
              onClick={handleRegister}
              loading={loading}
              disabled={!isFormValid() || loading}
              mt="md"
            >
              Create Account
            </Button>
          </Stack>

          <Box pt="md" style={{ borderTop: "1px solid var(--lnr-border)" }}>
            <Group justify="center" gap="xs">
              <Text size="sm" c="dimmed">
                Already have an account?
              </Text>
              <Button
                variant="subtle"
                size="xs"
                rightSection={<IconArrowRight size={14} />}
                onClick={() => { window.location.href = "/login"; }}
                disabled={loading}
                styles={{ root: { color: "var(--lnr-accent)", fontSize: rem(13), fontWeight: 500, padding: "0 4px", border: 0, height: rem(24) } }}
              >
                Sign In
              </Button>
            </Group>
          </Box>
        </Stack>
      </Paper>
    </Flex>
  );
}
