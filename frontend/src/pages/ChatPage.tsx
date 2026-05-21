import ChatWidget from '../components/Chat/ChatWidget';

export default function ChatPage() {
  return (
    <div className="p-4 md:p-6 h-[calc(100vh-4rem)] flex flex-col">
      <ChatWidget />
    </div>
  );
}
