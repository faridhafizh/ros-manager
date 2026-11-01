# ROS Manager UI

Next.js 14 (App Router) + Tailwind + shadcn-style components, Apple-style glass theme (light and dark).
Talks to the RouterOS v7 REST API through a server-side proxy (`app/api/ros/[...path]/route.ts`),
so router credentials never reach the browser.

## Run
```bash
bun install
Copy-Item .env.example .env.local
bun run dev
```

## Connect a router
1. Run this app on a computer connected to the same local network as the router.
2. On the router, enable neighbor discovery and `/ip service enable www-ssl`; create a read/write user.
3. Fill `ROS_USER` and `ROS_PASS` in `.env.local`, then choose a detected router from the router menu. A single discovered router is selected automatically.

`ROS_HOST` is optional and can remain unset. If one router is found, it is selected automatically and takes precedence over `ROS_HOST`; if several are found, choose one from the router menu. Discovery uses MikroTik MNDP over the local Layer 2 network and displays both IP and MAC addresses; REST management connects over the router's IP address, not its MAC address. The selected router must expose RouterOS REST through `www-ssl`. `ROS_SCHEME=http` can be set only when using the unencrypted `www` service.

## Layout
- `app/` pages: Dashboard, Interfaces, Firewall, Clients
- `components/ui.tsx` shared primitives, `components/shell.tsx` sidebar + theme toggle
- `lib/ros.ts` REST client + polling hook, `lib/mock.ts` demo router
