"use client";

import { useEffect, useState } from "react";
import {
  Title,
  Text,
  Box,
  Stack,
  Paper,
  Group,
  Badge,
  Button,
  Table,
  Modal,
  TextInput,
  Skeleton,
} from "@mantine/core";
import { IconPlus, IconTrash } from "@tabler/icons-react";
import { get, post, del } from "@/lib/backendRequests";
import type { AllowedImage } from "@/lib/types";
import { DisplayNotification } from "@/components/Notifications/component";

export default function ImagesPage() {
  const [images, setImages] = useState<AllowedImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [notification, setNotification] = useState<{ message: string; statusCode: number } | null>(null);

  const [imageName, setImageName] = useState("");
  const [tags, setTags] = useState("");
  const [description, setDescription] = useState("");

  const load = async () => {
    try {
      const res = await get("images/list");
      if (res.status === 200) setImages(res.data?.images || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!imageName) return;
    setCreating(true);
    try {
      const res = await post("images/add", { name: imageName, tags, description });
      setNotification({ message: res.message || "Image added", statusCode: res.status });
      if (res.status === 200) { setModalOpen(false); setImageName(""); setTags(""); setDescription(""); load(); }
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (imageId: number) => {
    try {
      const res = await del(`images/${imageId}`);
      setNotification({ message: res.message || "Image removed", statusCode: res.status });
      if (res.status === 200) load();
    } catch (err: any) {
      setNotification({ message: err.message, statusCode: 500 });
    }
  };

  return (
    <Stack gap="xl">
      <Group justify="space-between">
        <Box>
          <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Image Allowlist</Title>
          <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
            Platform-managed image overrides. Images from plugins are included automatically.
          </Text>
        </Box>
        <Button leftSection={<IconPlus size={14} />} size="sm" onClick={() => setModalOpen(true)}>
          Add Image
        </Button>
      </Group>

      {notification && (
        <DisplayNotification message={notification.message} statusCode={notification.statusCode} />
      )}

      <Paper>
        {loading ? (
          <Skeleton height={200} m="md" />
        ) : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Image Name</Table.Th>
                <Table.Th>Tags</Table.Th>
                <Table.Th>Description</Table.Th>
                <Table.Th>Source</Table.Th>
                <Table.Th></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {images.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={5}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No images in allowlist. Install a plugin to populate images automatically, or add manual overrides.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                images.map((img) => (
                  <Table.Tr key={img.id}>
                    <Table.Td><Text size="sm" fw={500}>{img.name}</Text></Table.Td>
                    <Table.Td>
                      <Group gap={4}>
                        {(img.tags || "").split(",").filter(Boolean).map((tag) => (
                          <Badge key={tag} variant="outline" size="xs">{tag.trim()}</Badge>
                        ))}
                      </Group>
                    </Table.Td>
                    <Table.Td><Text size="sm" c="dimmed">{img.description || "—"}</Text></Table.Td>
                    <Table.Td>
                      <Badge
                        color={img.source === "local" ? "accent" : "gray"}
                        variant="light"
                        size="xs"
                      >
                        {img.source}
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      {img.source === "local" && (
                        <Button
                          size="xs"
                          variant="subtle"
                          color="red"
                          leftSection={<IconTrash size={12} />}
                          onClick={() => handleDelete(img.id)}
                        >
                          Remove
                        </Button>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>

      <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Add Image Override">
        <Stack gap="md">
          <TextInput
            label="Image Name"
            placeholder="nginx, postgres, myorg/myapp"
            required
            value={imageName}
            onChange={(e) => setImageName(e.currentTarget.value)}
          />
          <TextInput
            label="Allowed Tags"
            placeholder="latest, 1.27, stable (comma-separated)"
            value={tags}
            onChange={(e) => setTags(e.currentTarget.value)}
          />
          <TextInput
            label="Description"
            placeholder="Optional description"
            value={description}
            onChange={(e) => setDescription(e.currentTarget.value)}
          />
          <Group justify="flex-end" mt="md">
            <Button variant="default" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={handleAdd} loading={creating} disabled={!imageName}>
              Add
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}
