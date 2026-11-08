"use client";

import { useRouter } from "next/navigation";
import EpisodePicker from "@/components/EpisodePicker";

export default function HomePage() {
  const router = useRouter();

  const handleSelect = async (episodeId: number) => {
    // POST /runs is handled inside the run page's useRunSocket hook.
    // We just route there — the hook will initiate the run on mount.
    router.push(`/run/${episodeId}`);
  };

  return <EpisodePicker onSelect={handleSelect} />;
}
