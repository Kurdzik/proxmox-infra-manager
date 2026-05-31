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
  Table,
  Skeleton,
  Anchor,
} from "@mantine/core";
import { get } from "@/lib/backendRequests";
import type { DockerService } from "@/lib/types";

export default function ServicesPage() {
  const [services, setServices] = useState<DockerService[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await get("services/list");
        if (res.status === 200) setServices(res.data?.services || []);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const statusColor = (s: string) =>
    s === "running" ? "green" : s === "stopped" ? "gray" : s === "deploying" ? "blue" : "red";

  return (
    <Stack gap="xl">
      <Box>
        <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>Service Registry</Title>
        <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
          Read-only view of all deployed services with their DNS and proxy configuration
        </Text>
      </Box>

      <Paper>
        {loading ? (
          <Skeleton height={200} m="md" />
        ) : (
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Service</Table.Th>
                <Table.Th>Image</Table.Th>
                <Table.Th>Target</Table.Th>
                <Table.Th>Port</Table.Th>
                <Table.Th>Domain</Table.Th>
                <Table.Th>Proxy</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {services.length === 0 ? (
                <Table.Tr>
                  <Table.Td colSpan={7}>
                    <Text size="sm" c="dimmed" ta="center" py="lg">
                      No services deployed.
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ) : (
                services.map((svc) => (
                  <Table.Tr key={svc.id}>
                    <Table.Td>
                      <Text size="sm" fw={500}>{svc.name}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">{svc.image_name}:{svc.image_tag}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        [{svc.target_type.toUpperCase()}] {svc.target_vmid}
                      </Text>
                    </Table.Td>
                    <Table.Td><Text size="sm">{svc.internal_port}</Text></Table.Td>
                    <Table.Td>
                      {svc.dns?.hostname ? (
                        <Text size="sm">{svc.dns.hostname}</Text>
                      ) : (
                        <Text size="sm" c="dimmed">—</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      {svc.nginx ? (
                        <Badge variant="outline" size="xs" color="accent">
                          {svc.nginx.proxy_type}
                        </Badge>
                      ) : (
                        <Text size="sm" c="dimmed">—</Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Badge color={statusColor(svc.status)} variant="light" size="xs">
                        {svc.status}
                      </Badge>
                    </Table.Td>
                  </Table.Tr>
                ))
              )}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
    </Stack>
  );
}
