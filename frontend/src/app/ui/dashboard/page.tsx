"use client";

import { useEffect, useState } from "react";
import {
  Title,
  Text,
  Box,
  Grid,
  Paper,
  Group,
  Stack,
  Badge,
  Skeleton,
} from "@mantine/core";
import {
  IconServer,
  IconDeviceDesktop,
  IconBrandDocker,
  IconPuzzle,
} from "@tabler/icons-react";
import { get } from "@/lib/backendRequests";
import type { Node, VM, DockerService, Plugin } from "@/lib/types";

interface StatCard {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
}

export default function DashboardPage() {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [vms, setVMs] = useState<VM[]>([]);
  const [services, setServices] = useState<DockerService[]>([]);
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [nodesRes, vmsRes, svcRes, pluginsRes] = await Promise.allSettled([
          get("nodes/list"),
          get("vms/list"),
          get("docker/list"),
          get("plugins/list"),
        ]);

        if (nodesRes.status === "fulfilled") setNodes(nodesRes.value.data?.nodes || []);
        if (vmsRes.status === "fulfilled") setVMs(vmsRes.value.data?.vms || []);
        if (svcRes.status === "fulfilled") setServices(svcRes.value.data?.services || []);
        if (pluginsRes.status === "fulfilled") setPlugins(pluginsRes.value.data?.plugins || []);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const stats: StatCard[] = [
    {
      label: "Nodes",
      value: nodes.length,
      icon: <IconServer size={20} stroke={1.5} />,
      color: "var(--lnr-accent)",
    },
    {
      label: "Virtual Machines",
      value: vms.length,
      icon: <IconDeviceDesktop size={20} stroke={1.5} />,
      color: "var(--lnr-success)",
    },
    {
      label: "Docker Services",
      value: services.length,
      icon: <IconBrandDocker size={20} stroke={1.5} />,
      color: "#06b6d4",
    },
    {
      label: "Plugins",
      value: plugins.length,
      icon: <IconPuzzle size={20} stroke={1.5} />,
      color: "#8b5cf6",
    },
  ];

  return (
    <Stack gap="xl">
      <Box>
        <Title order={3} mb={4} style={{ color: "var(--lnr-text)" }}>
          Dashboard
        </Title>
        <Text size="sm" style={{ color: "var(--lnr-text-muted)" }}>
          Overview of your Proxmox infrastructure
        </Text>
      </Box>

      <Grid>
        {stats.map((stat) => (
          <Grid.Col key={stat.label} span={{ base: 12, sm: 6, md: 3 }}>
            <Paper p="md" style={{ height: "100%" }}>
              {loading ? (
                <Skeleton height={80} />
              ) : (
                <Stack gap="xs">
                  <Box style={{ color: stat.color }}>{stat.icon}</Box>
                  <Text size="xl" fw={600} style={{ color: "var(--lnr-text)", lineHeight: 1 }}>
                    {stat.value}
                  </Text>
                  <Text size="xs" style={{ color: "var(--lnr-text-muted)" }}>
                    {stat.label}
                  </Text>
                </Stack>
              )}
            </Paper>
          </Grid.Col>
        ))}
      </Grid>

      <Grid>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Paper p="md">
            <Text size="sm" fw={600} mb="md" style={{ color: "var(--lnr-text)" }}>
              Cluster Nodes
            </Text>
            {loading ? (
              <Skeleton height={120} />
            ) : nodes.length === 0 ? (
              <Text size="sm" c="dimmed">No nodes synced yet</Text>
            ) : (
              <Stack gap="xs">
                {nodes.map((node) => (
                  <Group key={node.id} justify="space-between">
                    <Text size="sm">{node.name}</Text>
                    <Badge
                      color={node.status === "online" ? "green" : "red"}
                      variant="light"
                      size="xs"
                    >
                      {node.status}
                    </Badge>
                  </Group>
                ))}
              </Stack>
            )}
          </Paper>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 6 }}>
          <Paper p="md">
            <Text size="sm" fw={600} mb="md" style={{ color: "var(--lnr-text)" }}>
              Plugins
            </Text>
            {loading ? (
              <Skeleton height={120} />
            ) : plugins.length === 0 ? (
              <Text size="sm" c="dimmed">No plugins installed</Text>
            ) : (
              <Stack gap="xs">
                {plugins.map((plugin) => (
                  <Group key={plugin.id} justify="space-between">
                    <Text size="sm">{plugin.name}</Text>
                    <Badge
                      color={
                        plugin.status === "running"
                          ? "green"
                          : plugin.status === "stopped"
                          ? "gray"
                          : "red"
                      }
                      variant="light"
                      size="xs"
                    >
                      {plugin.status}
                    </Badge>
                  </Group>
                ))}
              </Stack>
            )}
          </Paper>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
