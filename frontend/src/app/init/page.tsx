"use client";

import { useState } from "react";
import {
  Title,
  Text,
  Button,
  TextInput,
  PasswordInput,
  Select,
  Stepper,
  Stack,
  Paper,
  Box,
  rem,
  Flex,
  Group,
  Switch,
  Alert,
} from "@mantine/core";
import {
  IconServer,
  IconKey,
  IconCheck,
  IconAlertCircle,
  IconServerBolt,
  IconCopy,
} from "@tabler/icons-react";
import { post } from "@/lib/backendRequests";
import { DisplayNotification } from "@/components/Notifications/component";

interface NotificationState {
  message: string;
  statusCode: number;
}

interface ConnectionTestResult {
  success: boolean;
  message: string;
  nodes?: string[];
}

export default function InitPage() {
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const [copiedPrepScript, setCopiedPrepScript] = useState(false);
  const [notification, setNotification] = useState<NotificationState | null>(null);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);

  const [proxmoxUrl, setProxmoxUrl] = useState("");
  const [proxmoxVersion, setProxmoxVersion] = useState("8");
  const [verifySsl, setVerifySsl] = useState(false);
  const [tokenId, setTokenId] = useState("");
  const [tokenSecret, setTokenSecret] = useState("");

  const testConnection = async () => {
    setLoading(true);
    setTestResult(null);
    try {
      const res = await post(
        "init/test-connection",
        { proxmox_url: proxmoxUrl, proxmox_version: proxmoxVersion, token_id: tokenId, token_secret: tokenSecret, verify_ssl: verifySsl },
        false,
      );
      if (res.status === 200) {
        setTestResult({ success: true, message: "Connection successful", nodes: res.data?.nodes });
      } else {
        setTestResult({ success: false, message: res.detail || "Connection failed" });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Connection failed" });
    } finally {
      setLoading(false);
    }
  };

  const handleConfigure = async () => {
    setLoading(true);
    try {
      const res = await post(
        "init/configure",
        { proxmox_url: proxmoxUrl, proxmox_version: proxmoxVersion, token_id: tokenId, token_secret: tokenSecret, verify_ssl: verifySsl },
        false,
      );
      if (res.status === 200) {
        setNotification({ message: "Platform configured successfully", statusCode: 200 });
        setTimeout(() => {
          window.location.href = "/register";
        }, 1500);
      } else {
        setNotification({ message: res.detail || "Configuration failed", statusCode: res.status });
      }
    } catch (err: any) {
      setNotification({ message: err.message || "Configuration failed", statusCode: 500 });
    } finally {
      setLoading(false);
    }
  };

  const step1Valid = proxmoxUrl.startsWith("https://") && proxmoxVersion;
  const step2Valid = tokenId && tokenSecret;
  const nodePrepScript = [
    "apt update",
    "apt install -y dnsmasq ifupdown2",
    "systemctl disable --now dnsmasq",
  ].join("\n");

  const copyNodePrepScript = async () => {
    await navigator.clipboard.writeText(nodePrepScript);
    setCopiedPrepScript(true);
    setTimeout(() => setCopiedPrepScript(false), 1600);
  };

  return (
    <Flex justify="center" align="center" style={{ minHeight: "100vh", width: "100%", padding: rem(24) }}>
      <Paper
        shadow="md"
        p="xl"
        radius={0}
        withBorder
        style={{
          width: "100%",
          maxWidth: rem(560),
          backgroundColor: "var(--lnr-surface)",
          border: "1px solid var(--lnr-border)",
        }}
      >
        <Stack gap="xl">
          <Box ta="center">
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
            <Title order={2} size="1.25rem" fw={600} mb="xs" style={{ color: "var(--lnr-text)" }}>
              Platform Setup
            </Title>
            <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
              Connect Infra Manager to your Proxmox VE cluster
            </Text>
          </Box>

          {notification && (
            <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
          )}

          <Stepper active={active} onStepClick={setActive} size="sm">
            <Stepper.Step
              label="Cluster"
              description="Proxmox endpoint"
              icon={<IconServer size={16} />}
            >
              <Stack gap="md" mt="lg">
                <TextInput
                  label="Proxmox URL"
                  placeholder="https://pve01.internal:8006"
                  required
                  value={proxmoxUrl}
                  onChange={(e) => setProxmoxUrl(e.currentTarget.value)}
                  description="HTTPS endpoint of your Proxmox cluster"
                />
                <Select
                  label="Proxmox VE Version"
                  required
                  value={proxmoxVersion}
                  onChange={(v) => setProxmoxVersion(v || "8")}
                  data={[
                    { value: "7", label: "Proxmox VE 7.x" },
                    { value: "8", label: "Proxmox VE 8.x" },
                  ]}
                  description="SDN DNS management requires PVE 8.x"
                />
                <Switch
                  label="Verify SSL certificate"
                  checked={verifySsl}
                  onChange={(e) => setVerifySsl(e.currentTarget.checked)}
                  description="Disable for self-signed certificates"
                />
                <Button
                  mt="md"
                  onClick={() => setActive(1)}
                  disabled={!step1Valid}
                  fullWidth
                >
                  Continue
                </Button>
              </Stack>
            </Stepper.Step>

            <Stepper.Step
              label="API Token"
              description="Authentication"
              icon={<IconKey size={16} />}
            >
              <Stack gap="md" mt="lg">
                <TextInput
                  label="Token ID"
                  placeholder="root@pam!infra-manager"
                  required
                  value={tokenId}
                  onChange={(e) => setTokenId(e.currentTarget.value)}
                  description="Format: user@realm!tokenname"
                />
                <PasswordInput
                  label="Token Secret"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  required
                  value={tokenSecret}
                  onChange={(e) => setTokenSecret(e.currentTarget.value)}
                />
                <Group grow>
                  <Button variant="default" onClick={() => setActive(0)}>
                    Back
                  </Button>
                  <Button onClick={() => setActive(2)} disabled={!step2Valid}>
                    Continue
                  </Button>
                </Group>
              </Stack>
            </Stepper.Step>

            <Stepper.Step
              label="Confirm"
              description="Test & apply"
              icon={<IconCheck size={16} />}
            >
              <Stack gap="md" mt="lg">
                <Box
                  style={{
                    padding: rem(12),
                    borderRadius: 4,
                    backgroundColor: "var(--lnr-elevated)",
                    border: "1px solid var(--lnr-border)",
                    fontSize: rem(12),
                    color: "var(--lnr-text-muted)",
                  }}
                >
                  <Text size="xs" fw={500} mb="xs" c="var(--lnr-text)">Configuration Summary</Text>
                  <Text size="xs">URL: {proxmoxUrl}</Text>
                  <Text size="xs">Version: PVE {proxmoxVersion}.x</Text>
                  <Text size="xs">Token: {tokenId}</Text>
                  <Text size="xs">SSL verification: {verifySsl ? "enabled" : "disabled"}</Text>
                </Box>

                <Box
                  style={{
                    border: "1px solid var(--lnr-border)",
                    borderRadius: 4,
                    overflow: "hidden",
                    backgroundColor: "var(--lnr-elevated)",
                  }}
                >
                  <Group
                    justify="space-between"
                    align="center"
                    px="sm"
                    py={8}
                    style={{ borderBottom: "1px solid var(--lnr-border)" }}
                  >
                    <Box>
                      <Text size="xs" fw={600} style={{ color: "var(--lnr-text)" }}>
                        Proxmox node preparation
                      </Text>
                      <Text size="xs" style={{ color: "var(--lnr-text-muted)" }}>
                        Run on every Proxmox node before provisioning SDN-backed VMs.
                      </Text>
                    </Box>
                    <Button
                      size="xs"
                      variant="subtle"
                      leftSection={<IconCopy size={12} />}
                      onClick={copyNodePrepScript}
                    >
                      {copiedPrepScript ? "Copied" : "Copy"}
                    </Button>
                  </Group>
                  <Box
                    component="pre"
                    m={0}
                    p="sm"
                    style={{
                      overflowX: "auto",
                      fontSize: rem(12),
                      lineHeight: 1.55,
                      color: "var(--lnr-text)",
                      backgroundColor: "var(--lnr-surface)",
                    }}
                  >
                    <code>{nodePrepScript}</code>
                  </Box>
                </Box>

                {testResult && (
                  <Alert
                    icon={testResult.success ? <IconCheck size={16} /> : <IconAlertCircle size={16} />}
                    color={testResult.success ? "green" : "red"}
                    variant="light"
                  >
                    <Text size="xs">{testResult.message}</Text>
                    {testResult.nodes && (
                      <Text size="xs" mt={4}>
                        Nodes found: {testResult.nodes.join(", ")}
                      </Text>
                    )}
                  </Alert>
                )}

                <Group grow>
                  <Button variant="default" onClick={() => setActive(1)}>
                    Back
                  </Button>
                  <Button variant="default" onClick={testConnection} loading={loading}>
                    Test Connection
                  </Button>
                  <Button
                    onClick={handleConfigure}
                    loading={loading}
                    disabled={!testResult?.success}
                  >
                    Apply
                  </Button>
                </Group>
              </Stack>
            </Stepper.Step>
          </Stepper>
        </Stack>
      </Paper>
    </Flex>
  );
}
