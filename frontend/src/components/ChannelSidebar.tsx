import { Channel } from '../api/client';

interface ChannelSidebarProps {
  channels: Channel[];
  selectedChannelId: string | null;
  onSelectChannel: (channelId: string | null) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export default function ChannelSidebar({
  channels,
  selectedChannelId,
  onSelectChannel,
  onRefresh,
  isRefreshing,
}: ChannelSidebarProps) {
  return (
    <div className="bg-neutral-800 rounded-2xl shadow-lg p-4 h-fit sticky top-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Channels</h2>
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-2 hover:bg-neutral-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Refresh subscriptions from YouTube"
        >
          <svg
            className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>

      <div className="space-y-1 max-h-[calc(100vh-12rem)] overflow-y-auto">
        <button
          onClick={() => onSelectChannel(null)}
          className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
            selectedChannelId === null
              ? 'bg-blue-600 text-white'
              : 'hover:bg-neutral-700 text-gray-300'
          }`}
        >
          <div className="flex items-center">
            <svg
              className="w-4 h-4 mr-2 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            <span className="text-sm font-medium truncate">All Channels</span>
          </div>
        </button>

        {channels.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            <p>No channels yet.</p>
            <p className="mt-2">Click refresh to sync from YouTube.</p>
          </div>
        ) : (
          channels.map((channel) => (
            <button
              key={channel.id}
              onClick={() => onSelectChannel(channel.channel_id)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                selectedChannelId === channel.channel_id
                  ? 'bg-blue-600 text-white'
                  : 'hover:bg-neutral-700 text-gray-300'
              }`}
              title={channel.channel_title}
            >
              <div className="flex items-center">
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-red-500 to-pink-500 flex-shrink-0 mr-2" />
                <span className="text-sm truncate">{channel.channel_title}</span>
              </div>
            </button>
          ))
        )}
      </div>

      {channels.length > 0 && (
        <div className="mt-4 pt-4 border-t border-neutral-700">
          <p className="text-xs text-gray-500 text-center">
            {channels.length} channel{channels.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  );
}
