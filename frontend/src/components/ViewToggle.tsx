interface ViewToggleProps {
  viewMode: 'grid' | 'list';
  onToggle: (mode: 'grid' | 'list') => void;
}

export default function ViewToggle({ viewMode, onToggle }: ViewToggleProps) {
  return (
    <div className="flex items-center gap-2 bg-neutral-800 rounded-lg p-1">
      <button
        onClick={() => onToggle('grid')}
        className={`px-4 py-2 rounded-md transition-colors flex items-center gap-2 ${
          viewMode === 'grid'
            ? 'bg-blue-600 text-white'
            : 'text-gray-400 hover:text-white hover:bg-neutral-700'
        }`}
        title="Grid view"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
          />
        </svg>
        <span className="text-sm font-medium">Grid</span>
      </button>

      <button
        onClick={() => onToggle('list')}
        className={`px-4 py-2 rounded-md transition-colors flex items-center gap-2 ${
          viewMode === 'list'
            ? 'bg-blue-600 text-white'
            : 'text-gray-400 hover:text-white hover:bg-neutral-700'
        }`}
        title="List view"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 6h16M4 12h16M4 18h16"
          />
        </svg>
        <span className="text-sm font-medium">List</span>
      </button>
    </div>
  );
}
