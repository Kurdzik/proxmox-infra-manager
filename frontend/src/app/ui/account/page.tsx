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
  Badge,
  Skeleton,
  Modal,
  TextInput,
  Textarea,
  ActionIcon,
  Alert,
  Table,
  Tooltip,
  CopyButton,
} from "@mantine/core";
import {
  IconLock,
  IconKey,
  IconPlus,
  IconTrash,
  IconDownload,
  IconAlertCircle,
  IconCheck,
  IconUpload,
} from "@tabler/icons-react";
import { get, post, del } from "@/lib/backendRequests";
import type { UserInfo, UserSSHKey } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function AccountPage() {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // Password change
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changing, setChanging] = useState(false);
  const [passwordNotification, setPasswordNotification] = useState<{ message: string; statusCode: number } | null>(null);

  // SSH Keys
  const [sshKeys, setSshKeys] = useState<UserSSHKey[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [keysNotification, setKeysNotification] = useState<{ message: string; statusCode: number } | null>(null);

  // Generate key modal
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [generateName, setGenerateName] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generatedPrivateKey, setGeneratedPrivateKey] = useState<string | null>(null);
  const [generatedKeyName, setGeneratedKeyName] = useState<string>("");

  // Import key modal
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importName, setImportName] = useState("");
  const [importPublicKey, setImportPublicKey] = useState("");
  const [importing, setImporting] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await get("users/me");
        if (res.status === 200) setUserInfo(res.data);
      } finally {
        setLoading(false);
      }
    };
    load();
    loadKeys();
  }, []);

  const loadKeys = async () => {
    setKeysLoading(true);
    try {
      const res = await get("keys/list");
      if (res.status === 200) setSshKeys(res.data?.keys || []);
    } finally {
      setKeysLoading(false);
    }
  };

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

  const openGenerateModal = () => {
    setGenerateName("");
    setGeneratedPrivateKey(null);
    setGeneratedKeyName("");
    setGenerateModalOpen(true);
  };

  const handleGenerateKey = async () => {
    if (!generateName.trim()) return;
    setGenerating(true);
    try {
      const res = await post("keys/generate", { name: generateName.trim() });
      if (res.status === 200) {
        setGeneratedPrivateKey(res.data?.private_key_pem || "");
        setGeneratedKeyName(res.data?.name || generateName);
        loadKeys();
      } else {
        setKeysNotification({ message: res.detail || "Failed to generate key", statusCode: res.status });
        setGenerateModalOpen(false);
      }
    } catch (err: any) {
      setKeysNotification({ message: err.message, statusCode: 500 });
      setGenerateModalOpen(false);
    } finally {
      setGenerating(false);
    }
  };

  const handleCloseGenerateModal = () => {
    setGenerateModalOpen(false);
    setGeneratedPrivateKey(null);
    setGeneratedKeyName("");
    setGenerateName("");
  };

  const openImportModal = () => {
    setImportName("");
    setImportPublicKey("");
    setImportModalOpen(true);
  };

  const handleImportKey = async () => {
    if (!importName.trim() || !importPublicKey.trim()) return;
    setImporting(true);
    try {
      const res = await post("keys/import", { name: importName.trim(), public_key: importPublicKey.trim() });
      setKeysNotification({ message: res.message || "Key imported", statusCode: res.status });
      if (res.status === 200) {
        setImportModalOpen(false);
        loadKeys();
      }
    } catch (err: any) {
      setKeysNotification({ message: err.message, statusCode: 500 });
    } finally {
      setImporting(false);
    }
  };

  const handleDeleteKey = async (keyId: number) => {
    try {
      const res = await del(`keys/${keyId}`);
      setKeysNotification({ message: res.message || "Key deleted", statusCode: res.status });
      if (res.status === 200) loadKeys();
    } catch (err: any) {
      setKeysNotification({ message: err.message, statusCode: 500 });
    }
  };

  const handleDownloadPrivateKey = async (keyId: number, keyName: string) => {
    try {
      const res = await get(`keys/${keyId}/private`);
      if (res.status === 200 && res.data?.private_key_pem) {
        const blob = new Blob([res.data.private_key_pem], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${keyName.replace(/\s+/g, "_")}.pem`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        setKeysNotification({ message: res.detail || "Could not retrieve private key", statusCode: res.status ?? 400 });
      }
    } catch (err: any) {
      setKeysNotification({ message: err.message, statusCode: 500 });
    }
  };

  const truncateKey = (key: string) => {
    const parts = key.split(" ");
    if (parts.length >= 2) {
      const keyBody = parts[1] || "";
      return `${parts[0]} ${keyBody.slice(0, 20)}...${keyBody.slice(-8)}`;
    }
    return key.slice(0, 40) + "...";
  };

  return (
    <Stack gap="xl">
      <Box>
        <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Account</Title>
        <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
          Manage your account settings and SSH keys
        </Text>
      </Box>

      {/* Account Info */}
      <Paper p="md">
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

      {/* Change Password */}
      <Paper p="md">
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

      {/* SSH Keys */}
      <Paper p="md">
        <Group justify="space-between" mb="md">
          <Box>
            <Text size="sm" fw={600} style={{ color: "var(--lnr-text)" }}>SSH Keys</Text>
            <Text size="xs" c="dimmed" mt={2}>
              Keys added here will be available to inject into VMs during provisioning.
            </Text>
          </Box>
          <Group gap="xs">
            <Button
              size="xs"
              variant="default"
              leftSection={<IconUpload size={12} />}
              onClick={openImportModal}
            >
              Import
            </Button>
            <Button
              size="xs"
              leftSection={<IconPlus size={12} />}
              onClick={openGenerateModal}
            >
              Generate keypair
            </Button>
          </Group>
        </Group>

        {keysNotification && (
          <Box mb="md">
            <DisplayNotification message={keysNotification.message} statusCode={keysNotification.statusCode} />
          </Box>
        )}

        {keysLoading ? (
          <Skeleton height={80} />
        ) : sshKeys.length === 0 ? (
          <Text size="sm" c="dimmed" ta="center" py="lg">
            No SSH keys yet. Generate a keypair or import a public key.
          </Text>
        ) : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Name</Table.Th>
                <Table.Th>Public Key</Table.Th>
                <Table.Th>Type</Table.Th>
                <Table.Th>Created</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sshKeys.map((key) => (
                <Table.Tr key={key.id}>
                  <Table.Td>
                    <Group gap="xs">
                      <IconKey size={13} color="var(--lnr-text-faint)" />
                      <Text size="sm" fw={500}>{key.name}</Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" ff="monospace" c="dimmed">{truncateKey(key.public_key)}</Text>
                  </Table.Td>
                  <Table.Td>
                    {key.has_private_key ? (
                      <Badge color="blue" variant="light" size="xs">keypair</Badge>
                    ) : (
                      <Badge color="gray" variant="light" size="xs">public only</Badge>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="xs" c="dimmed">{new Date(key.created_at).toLocaleDateString()}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap" justify="flex-end">
                      {key.has_private_key && (
                        <Tooltip label="Download private key">
                          <ActionIcon
                            size="sm"
                            variant="subtle"
                            color="blue"
                            onClick={() => handleDownloadPrivateKey(key.id, key.name)}
                          >
                            <IconDownload size={13} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                      <Tooltip label="Delete key">
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          color="red"
                          onClick={() => handleDeleteKey(key.id)}
                        >
                          <IconTrash size={13} />
                        </ActionIcon>
                      </Tooltip>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      {/* Generate keypair modal */}
      <Modal
        opened={generateModalOpen}
        onClose={handleCloseGenerateModal}
        title="Generate SSH Keypair"
        size="md"
      >
        {generatedPrivateKey ? (
          <Stack gap="md">
            <Alert icon={<IconAlertCircle size={16} />} color="orange" variant="light">
              <Text size="sm" fw={500}>Save your private key now</Text>
              <Text size="xs" mt={4}>
                This is the only time the private key will be shown. It is not stored in plain text.
              </Text>
            </Alert>
            <Box>
              <Text size="sm" fw={500} mb="xs">Private key for: {generatedKeyName}</Text>
              <Textarea
                value={generatedPrivateKey}
                readOnly
                autosize
                minRows={8}
                maxRows={16}
                styles={{ input: { fontFamily: "monospace", fontSize: 11 } }}
              />
            </Box>
            <Group justify="flex-end">
              <CopyButton value={generatedPrivateKey}>
                {({ copied, copy }) => (
                  <Button
                    leftSection={copied ? <IconCheck size={14} /> : undefined}
                    color={copied ? "green" : "blue"}
                    variant="light"
                    onClick={copy}
                  >
                    {copied ? "Copied!" : "Copy private key"}
                  </Button>
                )}
              </CopyButton>
              <Button onClick={handleCloseGenerateModal}>Done</Button>
            </Group>
          </Stack>
        ) : (
          <Stack gap="md">
            <TextInput
              label="Key Name"
              placeholder="e.g. my-laptop"
              required
              value={generateName}
              onChange={(e) => setGenerateName(e.currentTarget.value)}
              disabled={generating}
            />
            <Text size="xs" c="dimmed">
              An ed25519 keypair will be generated. The private key will be shown once — make sure to save it.
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={handleCloseGenerateModal} disabled={generating}>Cancel</Button>
              <Button
                leftSection={<IconKey size={14} />}
                onClick={handleGenerateKey}
                loading={generating}
                disabled={!generateName.trim()}
              >
                Generate
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      {/* Import public key modal */}
      <Modal
        opened={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        title="Import SSH Public Key"
        size="md"
      >
        <Stack gap="md">
          <TextInput
            label="Key Name"
            placeholder="e.g. work-laptop"
            required
            value={importName}
            onChange={(e) => setImportName(e.currentTarget.value)}
            disabled={importing}
          />
          <Textarea
            label="Public Key"
            placeholder="ssh-ed25519 AAAA... user@host"
            required
            value={importPublicKey}
            onChange={(e) => setImportPublicKey(e.currentTarget.value)}
            disabled={importing}
            minRows={3}
            styles={{ input: { fontFamily: "monospace", fontSize: 11 } }}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setImportModalOpen(false)} disabled={importing}>Cancel</Button>
            <Button
              leftSection={<IconUpload size={14} />}
              onClick={handleImportKey}
              loading={importing}
              disabled={!importName.trim() || !importPublicKey.trim()}
            >
              Import
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
