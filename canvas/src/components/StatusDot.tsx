"use client";

export const STATUS_COLORS: Record<string, string> = {
  online: "bg-green-500",
  offline: "bg-zinc-500",
  degraded: "bg-yellow-500",
  failed: "bg-red-500",
  provisioning: "bg-blue-500 animate-pulse",
};

export function StatusDot({
  status,
  size = "sm",
}: {
  status: string;
  size?: "sm" | "md";
}) {
  const sizeClass = size === "md" ? "w-2.5 h-2.5" : "w-2 h-2";
  return (
    <div
      className={`${sizeClass} rounded-full shrink-0 ${STATUS_COLORS[status] || "bg-zinc-600"}`}
    />
  );
}
