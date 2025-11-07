import { useState } from 'react';
import { FeedItem } from '../api/client';

interface VideoCardProps {
  video: FeedItem;
  viewMode?: 'grid' | 'list';
  onMarkWatched?: (video_id: string, channel_id: string) => Promise<void>;
  onUnmarkWatched?: (video_id: string) => Promise<void>;
}

export default function VideoCard({
  video,
  viewMode = 'grid',
  onMarkWatched,
  onUnmarkWatched,
}: VideoCardProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const publishedDate = new Date(video.published);
  const formattedDate = publishedDate.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const handleToggleWatched = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!onMarkWatched || !onUnmarkWatched || isUpdating) return;

    setIsUpdating(true);
    try {
      if (video.watched) {
        await onUnmarkWatched(video.video_id);
      } else {
        await onMarkWatched(video.video_id, video.channel_id);
      }
    } catch (error) {
      console.error('Failed to update watched status:', error);
    } finally {
      setIsUpdating(false);
    }
  };

  const handleLinkClick = async () => {
    // Auto-mark as watched when clicking the YouTube link
    if (!video.watched && onMarkWatched && !isUpdating) {
      try {
        await onMarkWatched(video.video_id, video.channel_id);
      } catch (error) {
        console.error('Failed to mark as watched:', error);
      }
    }
  };

  if (viewMode === 'list') {
    return (
      <div
        className={`bg-neutral-800 rounded-2xl shadow-lg overflow-hidden hover:bg-neutral-750 transition-all relative ${
          video.watched ? 'opacity-60' : ''
        }`}
      >
        {/* Watched indicator badge */}
        {video.watched && (
          <div className="absolute top-4 right-4 z-10 bg-green-600 rounded-full p-2 shadow-lg">
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-4 p-4">
          <div className="flex-shrink-0 w-full sm:w-80">
            <iframe
              className="w-full aspect-video rounded-lg"
              src={`https://www.youtube.com/embed/${video.video_id}`}
              title={video.title}
              allowFullScreen
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-lg mb-2 line-clamp-2">{video.title}</h3>
            <p className="text-sm text-gray-400 mb-2">{video.channel_title}</p>
            <p className="text-xs text-gray-500 mb-3">{formattedDate}</p>
            {video.description && (
              <p className="text-sm text-gray-300 line-clamp-3 mb-3">
                {video.description}
              </p>
            )}
            <div className="flex items-center gap-3">
              <a
                href={video.link}
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleLinkClick}
                className="inline-flex items-center text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                <svg
                  className="w-4 h-4 mr-1"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                  />
                </svg>
                Open on YouTube
              </a>

              {/* Mark/Unmark watched button */}
              {onMarkWatched && onUnmarkWatched && (
                <button
                  onClick={handleToggleWatched}
                  disabled={isUpdating}
                  className={`inline-flex items-center text-sm px-3 py-1 rounded-lg transition-colors ${
                    video.watched
                      ? 'bg-green-600 hover:bg-green-700 text-white'
                      : 'bg-neutral-700 hover:bg-neutral-600 text-gray-300'
                  } ${isUpdating ? 'opacity-50 cursor-not-allowed' : ''}`}
                  title={video.watched ? 'Mark as unwatched' : 'Mark as watched'}
                >
                  {isUpdating ? (
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                  ) : video.watched ? (
                    <>
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                      Watched
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                        />
                      </svg>
                      Mark watched
                    </>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`bg-neutral-800 rounded-2xl shadow-lg overflow-hidden hover:bg-neutral-750 transition-all relative ${
        video.watched ? 'opacity-60' : ''
      }`}
    >
      {/* Watched indicator badge */}
      {video.watched && (
        <div className="absolute top-3 right-3 z-10 bg-green-600 rounded-full p-1.5 shadow-lg">
          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      )}

      <div className="p-2">
        <iframe
          className="w-full aspect-video rounded-lg"
          src={`https://www.youtube.com/embed/${video.video_id}`}
          title={video.title}
          allowFullScreen
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        />
      </div>
      <div className="px-4 pb-4 pt-2">
        <h3 className="font-medium text-sm mb-1 line-clamp-2">{video.title}</h3>
        <p className="text-xs text-gray-400 mb-1">{video.channel_title}</p>
        <p className="text-xs text-gray-500 mb-2">{formattedDate}</p>
        <div className="flex items-center gap-2 flex-wrap">
          <a
            href={video.link}
            target="_blank"
            rel="noopener noreferrer"
            onClick={handleLinkClick}
            className="inline-flex items-center text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            <svg
              className="w-3 h-3 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
            YouTube
          </a>

          {/* Mark/Unmark watched button */}
          {onMarkWatched && onUnmarkWatched && (
            <button
              onClick={handleToggleWatched}
              disabled={isUpdating}
              className={`inline-flex items-center justify-center text-xs p-1.5 rounded transition-colors ${
                video.watched
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-neutral-700 hover:bg-neutral-600 text-gray-300'
              } ${isUpdating ? 'opacity-50 cursor-not-allowed' : ''}`}
              title={video.watched ? 'Mark as unwatched' : 'Mark as watched'}
            >
              {isUpdating ? (
                <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              ) : video.watched ? (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                  />
                </svg>
              ) : (
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
                  />
                </svg>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
