import { FeedItem } from '../api/client';

interface VideoCardProps {
  video: FeedItem;
  viewMode?: 'grid' | 'list';
}

export default function VideoCard({ video, viewMode = 'grid' }: VideoCardProps) {
  const publishedDate = new Date(video.published);
  const formattedDate = publishedDate.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  if (viewMode === 'list') {
    return (
      <div className="bg-neutral-800 rounded-2xl shadow-lg overflow-hidden hover:bg-neutral-750 transition-colors">
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
            <a
              href={video.link}
              target="_blank"
              rel="noopener noreferrer"
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
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-neutral-800 rounded-2xl shadow-lg overflow-hidden hover:bg-neutral-750 transition-colors">
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
        <a
          href={video.link}
          target="_blank"
          rel="noopener noreferrer"
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
      </div>
    </div>
  );
}
