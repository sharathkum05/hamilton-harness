import { AdminApp } from '@/admin/AdminApp'
import { ChatApp } from '@/chat/ChatApp'
import { Landing } from '@/landing/Landing'

// One bundle, routed by path: the product page, the dashboard and the chat panel.
export default function App() {
  const path = window.location.pathname
  if (path.startsWith('/admin')) return <AdminApp />
  if (path.startsWith('/chat')) return <ChatApp />
  return <Landing />
}
