import { Notification } from "@mantine/core";
import { IconCheck, IconAlertCircle } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface DisplayNotificationProps {
  message: string;
  statusCode: number;
}

export function DisplayNotification({ message, statusCode }: DisplayNotificationProps) {
  const [isVisible, setIsVisible] = useState(true);
  const [mounted, setMounted] = useState(false);

  const isSuccess = statusCode >= 200 && statusCode < 300;
  const isError = statusCode >= 400;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isError && !isSuccess) {
      setIsVisible(false);
      return;
    }
    setIsVisible(true);
    const timer = setTimeout(() => setIsVisible(false), 2000);
    return () => clearTimeout(timer);
  }, [statusCode, isError, isSuccess]);

  if (!isVisible || (!isError && !isSuccess) || !mounted) return null;

  const content = (
    <div
      style={{
        position: "fixed",
        bottom: "24px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 9999,
      }}
    >
      <Notification
        icon={isSuccess ? <IconCheck size={16} /> : <IconAlertCircle size={16} />}
        color={isSuccess ? "green" : "red"}
        title={isSuccess ? "Success" : "Error"}
        onClose={() => setIsVisible(false)}
      >
        {message}
      </Notification>
    </div>
  );

  return mounted ? createPortal(content, document.body) : null;
}
