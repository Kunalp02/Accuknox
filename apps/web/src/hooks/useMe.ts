import { useEffect, useState } from "react";
import { api } from "../api";

export function useMe() {
  const [me, setMe] = useState<{ email: string; role: string; org_id: string } | null>(null);

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  return me;
}
