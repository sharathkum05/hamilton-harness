import { AdminApp } from '@/admin/AdminApp'
import { ChatApp } from '@/chat/ChatApp'

// One bundle, routed by path: /admin is the dashboard, anything else the chat panel.
export default function App() {
  return window.location.pathname.startsWith('/admin') ? <AdminApp /> : <ChatApp />
}
