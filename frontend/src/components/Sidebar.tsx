"use client";

import { Box, Stack, Text, ScrollArea, Tooltip } from "@mantine/core";
import {
  IconLayoutDashboard,
  IconServer,
  IconDeviceDesktop,
  IconBrandDocker,
  IconNetwork,
  IconShield,
  IconPuzzle,
  IconPhoto,
  IconUser,
  IconLogout,
  IconChevronLeft,
  IconChevronRight,
  IconServerBolt,
  IconSettings,
} from "@tabler/icons-react";
import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import classes from "@/components/Sidebar.module.css";
import { removeAuthCookie } from "@/lib/cookies";

interface NavItem {
  icon: React.ReactNode;
  label: string;
  route?: string;
}

const infrastructureItems: NavItem[] = [
  { icon: <IconLayoutDashboard size={16} stroke={1.5} />, label: "Dashboard", route: "/ui/dashboard" },
  { icon: <IconServer size={16} stroke={1.5} />, label: "Nodes", route: "/ui/nodes" },
  { icon: <IconDeviceDesktop size={16} stroke={1.5} />, label: "Virtual Machines", route: "/ui/vms" },
];

const servicesItems: NavItem[] = [
  { icon: <IconBrandDocker size={16} stroke={1.5} />, label: "Docker Services", route: "/ui/docker" },
  { icon: <IconServerBolt size={16} stroke={1.5} />, label: "Service Registry", route: "/ui/services" },
  { icon: <IconNetwork size={16} stroke={1.5} />, label: "DNS", route: "/ui/dns" },
  { icon: <IconShield size={16} stroke={1.5} />, label: "Firewall", route: "/ui/firewall" },
];

const platformItems: NavItem[] = [
  { icon: <IconPuzzle size={16} stroke={1.5} />, label: "Plugins", route: "/ui/plugins" },
  { icon: <IconPhoto size={16} stroke={1.5} />, label: "Image Allowlist", route: "/ui/images" },
  { icon: <IconSettings size={16} stroke={1.5} />, label: "Settings", route: "/ui/settings" },
];

const bottomItems: NavItem[] = [
  { icon: <IconUser size={16} stroke={1.5} />, label: "Account", route: "/ui/account" },
  { icon: <IconLogout size={16} stroke={1.5} />, label: "Logout" },
];

interface SidebarItemProps {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  onClick?: () => void;
}

const SidebarItem = ({ item, active, collapsed, onClick }: SidebarItemProps) => {
  const inner = (
    <button className={classes.navItem} data-active={active || undefined} onClick={onClick}>
      <span className={classes.navItemIcon}>{item.icon}</span>
      {!collapsed && <span className={classes.navItemLabel}>{item.label}</span>}
    </button>
  );

  const wrapped = collapsed ? (
    <Tooltip label={item.label} position="right" offset={8}>
      {inner}
    </Tooltip>
  ) : (
    inner
  );

  if (item.route) {
    return (
      <Link href={item.route} style={{ textDecoration: "none", display: "block" }}>
        {wrapped}
      </Link>
    );
  }

  return wrapped;
};

export const SidebarComponent = () => {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = React.useState(false);

  React.useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved) setCollapsed(JSON.parse(saved));
  }, []);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("sidebar-collapsed", JSON.stringify(next));
  };

  const handleLogout = () => {
    removeAuthCookie();
    window.location.href = "/";
  };

  const groups = [
    { label: "Infrastructure", items: infrastructureItems },
    { label: "Services", items: servicesItems },
    { label: "Platform", items: platformItems },
  ];

  return (
    <Box
      className={classes.sidebarContainer}
      data-collapsed={collapsed || undefined}
      style={{ transition: "width 150ms ease" }}
    >
      <Box className={classes.sidebarHeader}>
        <Box className={classes.appIcon}>
          <IconServerBolt size={20} color="var(--lnr-accent)" stroke={1.5} />
        </Box>
        {!collapsed && <Text className={classes.appTitle}>Infra Manager</Text>}
        <Tooltip
          label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          position="right"
          offset={8}
        >
          <button
            onClick={toggleCollapsed}
            className={classes.headerAction}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <IconChevronRight size={14} stroke={1.8} />
            ) : (
              <IconChevronLeft size={14} stroke={1.8} />
            )}
          </button>
        </Tooltip>
      </Box>

      <ScrollArea className={classes.scrollArea}>
        <Stack gap={2}>
          {groups.map((group) => (
            <React.Fragment key={group.label}>
              {!collapsed && <Text className={classes.sectionLabel}>{group.label}</Text>}
              {group.items.map((item) => (
                <SidebarItem
                  key={item.label}
                  item={item}
                  active={!!item.route && pathname.startsWith(item.route)}
                  collapsed={collapsed}
                />
              ))}
            </React.Fragment>
          ))}
        </Stack>
      </ScrollArea>

      <Box className={classes.sidebarBottom}>
        <Stack gap={2}>
          {!collapsed && (
            <Text className={classes.sectionLabel} style={{ marginTop: 0 }}>
              Account
            </Text>
          )}
          {bottomItems.map((item) => (
            <SidebarItem
              key={item.label}
              item={item}
              active={!!item.route && pathname.startsWith(item.route)}
              collapsed={collapsed}
              onClick={item.label === "Logout" ? handleLogout : undefined}
            />
          ))}
        </Stack>
      </Box>
    </Box>
  );
};
