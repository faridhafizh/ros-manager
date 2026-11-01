# ROS Manager UI

A modern, web-based MikroTik RouterOS management interface built with **Next.js 14**, **Tailwind CSS**, and **shadcn-style UI components**.

ROS Manager UI provides a clean, responsive dashboard with an Apple-inspired glassmorphism design, supporting both light and dark themes. It communicates with MikroTik RouterOS v7 through a server-side REST API proxy, keeping router credentials securely on the server rather than exposing them to the browser.

## ✨ Features

- **Modern Dashboard** — Clean and responsive interface for router management.
- **Apple-Inspired Glass UI** — Glassmorphism design with light and dark themes.
- **RouterOS v7 Integration** — Communicates with MikroTik devices through the RouterOS REST API.
- **Automatic Router Discovery** — Detects MikroTik routers on the local Layer 2 network using MNDP.
- **Multi-Router Support** — Discover multiple routers and select the device you want to manage.
- **Secure Server-Side Proxy** — Router credentials remain server-side and are never directly exposed to the browser.
- **Real-Time Data Polling** — Retrieves router information through the shared REST client and polling hook.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Next.js 14 | React framework with App Router |
| React | User interface |
| Tailwind CSS | Styling and responsive layouts |
| shadcn-style components | Reusable UI primitives |
| Bun | Package manager and runtime |
| RouterOS v7 REST API | Router management and communication |
| MikroTik MNDP | Local network router discovery |

## 📸 Application Modules

The application currently includes the following management sections:

| Module | Description |
|---|---|
| Dashboard | Router overview and system information |
| Interfaces | Network interface monitoring and management |
| Firewall | Firewall configuration and management |
| Clients | Connected client information |

## 🚀 Getting Started

### Prerequisites

Before installing, make sure you have:

- [Bun](https://bun.sh/) installed.
- Node.js compatible with your Next.js environment.
- A MikroTik router running RouterOS v7.
- Network connectivity between the application server and the router.
- RouterOS REST API access enabled.

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/YOUR_USERNAME/ros-manager-ui.git
cd ros-manager-ui
```

**2. Install dependencies**

```bash
bun install
```

**3. Configure environment variables**

Create your local environment configuration:

```powershell
Copy-Item .env.example .env.local
```

On Linux or macOS:

```bash
cp .env.example .env.local
```

**4. Start the development server**

```bash
bun run dev
```

**5. Open the application**

Navigate to:

```text
http://localhost:3000
```

## ⚙️ Router Configuration

ROS Manager UI connects to MikroTik routers through the RouterOS v7 REST API.

### 1. Prepare your MikroTik router

On your MikroTik router:

- Enable MikroTik Neighbor Discovery Protocol (MNDP) on the relevant local network interface.
- Enable the HTTPS management service:

```routeros
/ip service enable www-ssl
```

- Create a dedicated RouterOS user with the permissions required for the management operations you intend to use.

**Security recommendation:** Use a dedicated account with the minimum required permissions. Avoid using the default `admin` account.

### 2. Configure environment variables

Set your router credentials in `.env.local`:

```env
ROS_USER=your_router_username
ROS_PASS=your_router_password
```

Optionally, configure a static router host:

```env
ROS_HOST=192.168.88.1
```

For HTTPS connections, use the default scheme or configure:

```env
ROS_SCHEME=https
```

For HTTP connections, only when using the unencrypted RouterOS `www` service:

```env
ROS_SCHEME=http
```

Never commit `.env.local` or expose router credentials through client-side environment variables.

### 3. Router discovery and selection

The application supports automatic MikroTik router discovery through MNDP over the local Layer 2 network.

Discovery behavior:

- **Single router detected:** Automatically selects the discovered router.
- **Multiple routers detected:** Displays available routers in the router selection menu.
- **No router detected:** Check network connectivity, MNDP configuration, and Layer 2 accessibility.

Discovered routers display both IP and MAC addresses.

> **Important:** RouterOS REST API management connects through the router's IP address, not its MAC address. The selected router must have the REST API available through the `www-ssl` service.

### Router selection priority

| Scenario | Behavior |
|---|---|
| One router discovered | Automatically selected |
| Multiple routers discovered | User selects a router |
| `ROS_HOST` configured | Used as an optional host configuration, subject to discovery selection behavior |

When a router is discovered, automatic discovery selection takes precedence over `ROS_HOST`.

## 🔐 Security Architecture

The application uses a server-side API proxy to communicate with MikroTik RouterOS.

```text
┌──────────────────────┐
│      Web Browser     │
│                      │
│   Next.js Interface  │
└──────────┬───────────┘
           │
           │ HTTP Requests
           ▼
┌──────────────────────┐
│    Next.js Server    │
│                      │
│   API Route Proxy    │
│   /api/ros/[...path] │
└──────────┬───────────┘
           │
           │ RouterOS REST API
           ▼
┌──────────────────────┐
│   MikroTik Router    │
│                      │
│     RouterOS v7      │
└──────────────────────┘
```

Security considerations:

- Router credentials are stored in server-side environment variables.
- API communication is handled through Next.js server-side routes.
- The browser does not directly receive RouterOS credentials.
- HTTPS (`www-ssl`) is recommended for router communication.
- Use a dedicated RouterOS account with restricted permissions.

**Note:** Server-side credential handling reduces browser-side exposure but does not replace application authentication, authorization, or network-level access controls. Do not expose the management interface publicly without implementing appropriate protections.

## 📁 Project Structure

```text
ros-manager-ui/
│
├── app/
│   ├── api/
│   │   └── ros/
│   │       └── [...path]/
│   │           └── route.ts
│   │
│   ├── dashboard/
│   ├── interfaces/
│   ├── firewall/
│   ├── clients/
│   └── ...
│
├── components/
│   ├── ui.tsx
│   └── shell.tsx
│
├── lib/
│   ├── ros.ts
│   └── mock.ts
│
├── .env.example
├── .gitignore
├── package.json
├── tailwind.config.ts
└── README.md
```

### Core Components

| File | Responsibility |
|---|---|
| `app/` | Application pages and API routes |
| `app/api/ros/[...path]/route.ts` | Server-side RouterOS REST API proxy |
| `components/ui.tsx` | Shared UI primitives and reusable components |
| `components/shell.tsx` | Application layout, sidebar, and theme switching |
| `lib/ros.ts` | RouterOS REST API client and polling hook |
| `lib/mock.ts` | Mock router data for demonstration and development |

## 🧪 Development

Start the development environment:

```bash
bun run dev
```

Build the application:

```bash
bun run build
```

Run the production server:

```bash
bun run start
```

## 🗺️ Roadmap

Potential future improvements:

- [ ] Advanced router monitoring and system statistics
- [ ] Real-time interface traffic visualization
- [ ] Wireless network management
- [ ] DHCP server and lease management
- [ ] NAT and firewall rule management
- [ ] User authentication and role-based access control
- [ ] Multi-router management enhancements
- [ ] System logs and event monitoring
- [ ] Responsive mobile management experience

## 🤝 Contributing

Contributions, feature requests, and bug reports are welcome.

If you would like to contribute:

1. Fork this repository.
2. Create a feature branch.
3. Commit your changes.
4. Push your branch.
5. Open a Pull Request.

Please provide clear descriptions of your changes and include relevant screenshots when submitting UI improvements.

<p align="center">
  Built with ❤️ for MikroTik and RouterOS enthusiasts.
</p>

<p align="center">
  <sub>ROS Manager UI — Modern RouterOS Management, Simplified.</sub>
</p>
