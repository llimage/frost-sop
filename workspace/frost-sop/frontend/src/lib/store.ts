import { create } from "zustand";

interface AppState {
  currentProjectId: string;
  currentMode: "dev" | "create" | "client";
  logs: string[];
  addLog: (message: string) => void;
  clearLogs: () => void;
  setProject: (id: string) => void;
  setMode: (mode: "dev" | "create" | "client") => void;
}

export const useStore = create<AppState>((set) => ({
  currentProjectId: "default",
  currentMode: "dev",
  logs: [],
  addLog: (message) =>
    set((state) => ({
      logs: [
        ...state.logs,
        `[${new Date().toLocaleTimeString("zh-CN", { hour12: false })}] ${message}`,
      ],
    })),
  clearLogs: () => set({ logs: [] }),
  setProject: (id) => set({ currentProjectId: id }),
  setMode: (mode) => set({ currentMode: mode }),
}));
