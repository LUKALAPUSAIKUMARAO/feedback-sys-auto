"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const token = Cookies.get("access_token");
    router.replace(token ? "/admin/dashboard" : "/admin/login");
  }, [router]);
  return null;
}
