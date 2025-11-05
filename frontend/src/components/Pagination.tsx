interface PaginationProps {
  nextCursor: string | null;
  onPrevious: () => void;
  onNext: () => void;
  hasPrevious: boolean;
  currentPage: number;
}

export default function Pagination({
  nextCursor,
  onPrevious,
  onNext,
  hasPrevious,
  currentPage,
}: PaginationProps) {
  return (
    <div className="flex items-center justify-center gap-4 mt-8 mb-8">
      <button
        onClick={onPrevious}
        disabled={!hasPrevious}
        className="px-6 py-3 bg-neutral-800 hover:bg-neutral-700 disabled:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors flex items-center gap-2"
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
            d="M15 19l-7-7 7-7"
          />
        </svg>
        Previous
      </button>

      <div className="px-4 py-2 bg-neutral-800 rounded-lg">
        <span className="text-sm text-gray-400">Page {currentPage}</span>
      </div>

      <button
        onClick={onNext}
        disabled={!nextCursor}
        className="px-6 py-3 bg-neutral-800 hover:bg-neutral-700 disabled:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors flex items-center gap-2"
      >
        Next
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
            d="M9 5l7 7-7 7"
          />
        </svg>
      </button>
    </div>
  );
}
