"use client";

import { useEffect } from "react";
import { get } from "@/lib/backendRequests";
import { isAuthenticated } from "@/lib/cookies";

export default function RootRedirect() {
  useEffect(() => {
    const redirect = async () => {
      try {
        const res = await get("init/status", false);
        if (res.status === 200 && res.data?.is_initialized === false) {
          window.location.href = "/init";
          return;
        }
      } catch {
        // If the backend is unreachable, still try to go to init
        window.location.href = "/init";
        return;
      }

      if (!isAuthenticated()) {
        window.location.href = "/login";
        return;
      }

      window.location.href = "/ui/dashboard";
    };

    redirect();
  }, []);

  return <></>;
}
