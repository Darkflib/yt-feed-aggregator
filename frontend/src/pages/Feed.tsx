import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type User, type Channel, type FeedItem } from '../api/client';
import VideoCard from '../components/VideoCard';
import ChannelSidebar from '../components/ChannelSidebar';
import Pagination from '../components/Pagination';
import ViewToggle from '../components/ViewToggle';

export default function Feed() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [feedItems, setFeedItems] = useState<FeedItem[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pagination state
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [currentPage, setCurrentPage] = useState(1);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const loadFeed = useCallback(async (cursor: string | null) => {
    try {
      setError(null);
      const feedData = await api.getFeed({
        limit: 24,
        cursor,
        channel_id: selectedChannelId,
      });

      setFeedItems(feedData.items);
      setNextCursor(feedData.next_cursor);
    } catch (err) {
      console.error('Failed to load feed:', err);
      setError(err instanceof Error ? err.message : 'Failed to load feed');
    }
  }, [selectedChannelId]);

  const loadUserAndChannels = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const userData = await api.getMe();
      setUser(userData);

      const subscriptionsData = await api.getSubscriptions();
      setChannels(subscriptionsData.channels);

      // Load initial feed
      await loadFeed(null);
    } catch (err) {
      console.error('Failed to load user data:', err);
      // If unauthorized, redirect to login
      if (err instanceof Error && err.message.includes('401')) {
        navigate('/login');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      }
    } finally {
      setIsLoading(false);
    }
  }, [navigate, loadFeed]);

  // Load user and channels on mount
  useEffect(() => {
    loadUserAndChannels();
  }, [loadUserAndChannels]);

  // Load feed when channel filter changes
  useEffect(() => {
    if (user) {
      resetPagination();
      loadFeed(null);
    }
  }, [selectedChannelId, user, loadFeed]);

  const handleRefreshSubscriptions = async () => {
    try {
      setIsRefreshing(true);
      setError(null);

      const result = await api.refreshSubscriptions();
      const subscriptionsData = await api.getSubscriptions();
      setChannels(subscriptionsData.channels);

      // Reload feed after refresh
      resetPagination();
      await loadFeed(null);

      console.log(`Synced ${result.count} channels from YouTube`);
    } catch (err) {
      console.error('Failed to refresh subscriptions:', err);
      setError(err instanceof Error ? err.message : 'Failed to refresh subscriptions');
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
      navigate('/login');
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  const resetPagination = () => {
    setCursors([null]);
    setCurrentPage(1);
    setNextCursor(null);
  };

  const handleNextPage = async () => {
    if (nextCursor) {
      const newCursors = [...cursors, nextCursor];
      setCursors(newCursors);
      setCurrentPage(currentPage + 1);
      await loadFeed(nextCursor);
    }
  };

  const handlePreviousPage = async () => {
    if (currentPage > 1) {
      const newPage = currentPage - 1;
      const cursor = cursors[newPage - 1];
      setCurrentPage(newPage);
      setCursors(cursors.slice(0, newPage));
      await loadFeed(cursor);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-neutral-900 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
          <p className="text-gray-400">Loading your feed...</p>
        </div>
      </div>
    );
  }

  if (error && !user) {
    return (
      <div className="min-h-screen bg-neutral-900 flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="bg-red-900/20 border border-red-500 rounded-lg p-6 mb-4">
            <p className="text-red-400">{error}</p>
          </div>
          <button
            onClick={() => navigate('/login')}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-900">
      {/* Header */}
      <header className="bg-neutral-800 shadow-lg sticky top-0 z-10">
        <div className="max-w-screen-2xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <svg
                className="w-8 h-8 text-red-500"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
              </svg>
              <h1 className="text-xl font-bold">YouTube Feed</h1>
            </div>

            <div className="flex items-center gap-4">
              <ViewToggle viewMode={viewMode} onToggle={setViewMode} />

              {user && (
                <div className="flex items-center gap-3">
                  {user.avatar_url && (
                    <img
                      src={user.avatar_url}
                      alt={user.display_name}
                      className="w-8 h-8 rounded-full"
                    />
                  )}
                  <span className="text-sm text-gray-300 hidden sm:inline">
                    {user.display_name}
                  </span>
                  <button
                    onClick={handleLogout}
                    className="px-4 py-2 text-sm bg-neutral-700 hover:bg-neutral-600 rounded-lg transition-colors"
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="max-w-screen-2xl mx-auto px-4 py-6">
        {error && (
          <div className="mb-6 bg-red-900/20 border border-red-500 rounded-lg p-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        <div className="flex flex-col lg:flex-row gap-6">
          {/* Sidebar */}
          <aside className="lg:w-64 flex-shrink-0">
            <ChannelSidebar
              channels={channels}
              selectedChannelId={selectedChannelId}
              onSelectChannel={setSelectedChannelId}
              onRefresh={handleRefreshSubscriptions}
              isRefreshing={isRefreshing}
            />
          </aside>

          {/* Feed */}
          <main className="flex-1 min-w-0">
            {feedItems.length === 0 ? (
              <div className="text-center py-16">
                <svg
                  className="w-16 h-16 text-gray-600 mx-auto mb-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
                <h3 className="text-xl font-semibold text-gray-400 mb-2">
                  No videos found
                </h3>
                <p className="text-gray-500">
                  {channels.length === 0
                    ? 'Click "Refresh" in the sidebar to sync your YouTube subscriptions.'
                    : 'Try selecting a different channel or refreshing your subscriptions.'}
                </p>
              </div>
            ) : (
              <>
                <div
                  className={
                    viewMode === 'grid'
                      ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6'
                      : 'space-y-6'
                  }
                >
                  {feedItems.map((item) => (
                    <VideoCard
                      key={item.video_id}
                      video={item}
                      viewMode={viewMode}
                    />
                  ))}
                </div>

                <Pagination
                  nextCursor={nextCursor}
                  onNext={handleNextPage}
                  onPrevious={handlePreviousPage}
                  hasPrevious={currentPage > 1}
                  currentPage={currentPage}
                />
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
