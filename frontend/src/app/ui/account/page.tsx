"use client";

import { useEffect, useState } from "react";
import {
  Title,
  Text,
  Box,
  Stack,
  Paper,
  Group,
  Button,
  PasswordInput,
  TextInput,
  Select,
  Switch,
  Badge,
  Skeleton,
  Alert,
  Divider,
} from "@mantine/core";
import { IconLock, IconServer, IconCheck, IconAlertCircle } from "@tabler/icons-react";
import { get, post } from "@/lib/backendRequests";
import type { UserInfo, PlatformConfig } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

interface ConnectionTestResult {
  success: boolean;
  message: string;
  nodes?: string[];
}

export default function AccountPage() {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // Password change
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changing, setChanging] = useState(false);
  const [passwordNotification, setPasswordNotification] = useState<{ message: string; statusCode: number } | null>(null);

  // Proxmox connection
  const [proxmoxUrl, setProxmoxUrl] = useState("");
  const [proxmoxVersion, setProxmoxVersion] = useState("8");
  const [tokenId, setTokenId] = useState("");
  const [tokenSecret, setTokenSecret] = useState("");
  const [verifySsl, setVerifySsl] = useState(false);
  const [proxmoxLoading, setProxmoxLoading] = useState(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);
  const [proxmoxNotification, setProxmoxNotification] = useState<{ message: string; statusCode: number } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await get("users/me");
        if (res.status === 200) {
          setUserInfo(res.data);
          if (res.data?.is_admin) {
            const cfg = await get("init/config");
            if (cfg.status === 200 && cfg.data) {
              setProxmoxUrl(cfg.data.proxmox_url || "");
              setProxmoxVersion(cfg.data.proxmox_version || "8");
              setTokenId(cfg.data.token_id || "");
              setVerifySsl(cfg.data.verify_ssl ?? false);
            }
          }
        }
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const isPasswordFormValid = () =>
    currentPassword && newPassword && newPassword === confirmPassword && newPassword.length >= 8;

  const handleChangePassword = async () => {
    if (!isPasswordFormValid()) return;
    setChanging(true);
    try {
      const res = await post("users/change-password", {
        old_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordNotification({ message: res.message || "Password changed", statusCode: res.status });
      if (res.status === 200) {
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      }
    } catch (err: any) {
      setPasswordNotification({ message: err.message, statusCode: 500 });
    } finally {
      setChanging(false);
    }
  };

  const isProxmoxFormValid = () =>
    proxmoxUrl.startsWith("https://") && proxmoxVersion && tokenId && tokenSecret;

  const handleTestConnection = async () => {
    setProxmoxLoading(true);
    setTestResult(null);
    try {
      const res = await post("init/test-connection", {
        proxmox_url: proxmoxUrl,
        proxmox_version: proxmoxVersion,
        token_id: tokenId,
        token_secret: tokenSecret,
        verify_ssl: verifySsl,
      });
      if (res.status === 200) {
        setTestResult({ success: true, message: "Connection successful", nodes: res.data?.nodes });
      } else {
        setTestResult({ success: false, message: res.detail || "Connection failed" });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Connection failed" });
    } finally {
      setProxmoxLoading(false);
    }
  };

  const handleSaveProxmox = async () => {
    setProxmoxLoading(true);
    setProxmoxNotification(null);
    try {
      const res = await post("init/configure", {
        proxmox_url: proxmoxUrl,
        proxmox_version: proxmoxVersion,
        token_id: tokenId,
        token_secret: tokenSecret,
        verify_ssl: verifySsl,
      });
      setProxmoxNotification({ message: res.message || "Configuration saved", statusCode: res.status });
      if (res.status === 200) {
        setTokenSecret("");
        setTestResult(null);
      }
    } catch (err: any) {
      setProxmoxNotification({ message: err.message, statusCode: 500 });
    } finally {
      setProxmoxLoading(false);
    }
  };

  return (
    <Stack gap="xl">
      <Box>
        <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Account</Title>
        <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
          Manage your account settings
        </Text>
      </Box>

      <Paper p="md" style={{ maxWidth: 480 }}>
        <Text size="sm" fw={600} mb="md" style={{ color: "var(--lnr-text)" }}>
          Account Info
        </Text>
        {loading ? (
          <Skeleton height={60} />
        ) : (
          <Stack gap="xs">
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Username</Text>
              <Text size="sm" fw={500}>{userInfo?.username}</Text>
            </Group>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Tenant ID</Text>
              <Text size="sm" ff="monospace" style={{ fontSize: 11 }}>{userInfo?.tenant_id}</Text>
            </Group>
            <Group justify="space-between">
              <Text size="sm" c="dimmed">Role</Text>
              {userInfo?.is_admin ? (
                <Badge color="accent" variant="light" size="xs">Admin</Badge>
              ) : (
                <Badge color="gray" variant="light" size="xs">User</Badge>
              )}
            </Group>
          </Stack>
        )}
      </Paper>

      <Paper p="md" style={{ maxWidth: 480 }}>
        <Text size="sm" fw={600} mb="md" style={{ color: "var(--lnr-text)" }}>
          Change Password
        </Text>
        {passwordNotification && (
          <Box mb="md">
            <DisplayNotification message={passwordNotification.message} statusCode={passwordNotification.statusCode} />
          </Box>
        )}
        <Stack gap="md">
          <PasswordInput
            label="Current Password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.currentTarget.value)}
            disabled={changing}
          />
          <PasswordInput
            label="New Password"
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.currentTarget.value)}
            disabled={changing}
            error={newPassword && newPassword.length < 8 ? "Minimum 8 characters" : undefined}
          />
          <PasswordInput
            label="Confirm New Password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.currentTarget.value)}
            disabled={changing}
            error={confirmPassword && newPassword !== confirmPassword ? "Passwords do not match" : undefined}
          />
          <Button
            leftSection={<IconLock size={14} />}
            onClick={handleChangePassword}
            loading={changing}
            disabled={!isPasswordFormValid()}
            style={{ alignSelf: "flex-start" }}
          >
            Change Password
          </Button>
        </Stack>
      </Paper>

      {userInfo?.is_admin && (
        <Paper p="md" style={{ maxWidth: 480 }}>
          <Text size="sm" fw={600} mb={4} style={{ color: "var(--lnr-text)" }}>
            Proxmox Connection
          </Text>
          <Text size="xs" c="dimmed" mb="md">
            Update the Proxmox VE cluster credentials. A new token secret is required to save changes.
          </Text>
          {proxmoxNotification && (
            <Box mb="md">
              <DisplayNotification message={proxmoxNotification.message} statusCode={proxmoxNotification.statusCode} />
            </Box>
          )}
          {loading ? (
            <Skeleton height={200} />
          ) : (
            <Stack gap="md">
              <TextInput
                label="Proxmox URL"
                placeholder="https://pve01.internal:8006"
                required
                value={proxmoxUrl}
                onChange={(e) => { setProxmoxUrl(e.currentTarget.value); setTestResult(null); }}
                description="HTTPS endpoint of your Proxmox cluster"
                disabled={proxmoxLoading}
              />
              <Select
                label="Proxmox VE Version"
                required
                value={proxmoxVersion}
                onChange={(v) => { setProxmoxVersion(v || "8"); setTestResult(null); }}
                data={[
                  { value: "7", label: "Proxmox VE 7.x" },
                  { value: "8", label: "Proxmox VE 8.x" },
                ]}
                disabled={proxmoxLoading}
              />
              <TextInput
                label="Token ID"
                placeholder="root@pam!infra-manager"
                required
                value={tokenId}
                onChange={(e) => { setTokenId(e.currentTarget.value); setTestResult(null); }}
                description="Format: user@realm!tokenname"
                disabled={proxmoxLoading}
              />
              <PasswordInput
                label="Token Secret"
                placeholder="Enter new token secret to apply changes"
                required
                value={tokenSecret}
                onChange={(e) => { setTokenSecret(e.currentTarget.value); setTestResult(null); }}
                disabled={proxmoxLoading}
              />
              <Switch
                label="Verify SSL certificate"
                checked={verifySsl}
                onChange={(e) => { setVerifySsl(e.currentTarget.checked); setTestResult(null); }}
                description="Disable for self-signed certificates"
                disabled={proxmoxLoading}
              />

              {testResult && (
                <Alert
                  icon={testResult.success ? <IconCheck size={16} /> : <IconAlertCircle size={16} />}
                  color={testResult.success ? "green" : "red"}
                  variant="light"
                >
                  <Text size="xs">{testResult.message}</Text>
                  {testResult.nodes && testResult.nodes.length > 0 && (
                    <Text size="xs" mt={4}>Nodes: {testResult.nodes.join(", ")}</Text>
                  )}
                </Alert>
              )}

              <Group>
                <Button
                  variant="default"
                  leftSection={<IconServer size={14} />}
                  onClick={handleTestConnection}
                  loading={proxmoxLoading}
                  disabled={!isProxmoxFormValid()}
                >
                  Test Connection
                </Button>
                <Button
                  leftSection={<IconCheck size={14} />}
                  onClick={handleSaveProxmox}
                  loading={proxmoxLoading}
                  disabled={!testResult?.success}
                >
                  Save
                </Button>
              </Group>
            </Stack>
          )}
        </Paper>
      )}
    </Stack>
  );
}
