import type { Config } from "tailwindcss";
const c = (v: string) => `rgb(var(--${v}) / <alpha-value>)`;
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { fg: c("fg"), muted: c("muted"), accent: c("accent"), ok: c("ok"), warn: c("warn"), danger: c("danger") },
    },
  },
  plugins: [],
};
export default config;
