import React from 'react';
import { useSettings } from '../hooks/useSettings';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { settings, updateSetting } = useSettings();

  if (!isOpen) return null;

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
      onClick={handleOverlayClick}
    >
      <div className="bg-neutral-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-neutral-700">
          <h2 className="text-2xl font-semibold text-white">Settings</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-2 rounded-lg hover:bg-neutral-700"
            aria-label="Close settings"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Settings Content */}
        <div className="p-6 space-y-6">
          {/* Download Features Section */}
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Download Features</h3>
            <div className="space-y-4">
              {/* Enable Download Buttons Toggle */}
              <div className="flex items-start justify-between p-4 bg-neutral-750 rounded-xl">
                <div className="flex-1">
                  <label
                    htmlFor="enable-download-buttons"
                    className="text-white font-medium cursor-pointer"
                  >
                    Enable Download Buttons
                  </label>
                  <p className="text-sm text-gray-400 mt-1">
                    Show a download button on each video card that copies a yt-dlp command to your
                    clipboard. The command includes metadata, thumbnail, and subtitle downloads.
                  </p>
                </div>
                <div className="ml-4">
                  <button
                    id="enable-download-buttons"
                    role="switch"
                    aria-checked={settings.enableDownloadButtons}
                    onClick={() =>
                      updateSetting('enableDownloadButtons', !settings.enableDownloadButtons)
                    }
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-neutral-800 ${
                      settings.enableDownloadButtons ? 'bg-blue-600' : 'bg-neutral-600'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        settings.enableDownloadButtons ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>
            </div>
          </section>

          {/* Account Settings Section (Placeholder) */}
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Account Settings</h3>
            <div className="space-y-3 opacity-50">
              <div className="flex items-center justify-between p-4 bg-neutral-750 rounded-xl cursor-not-allowed">
                <div className="flex items-center gap-3">
                  <svg
                    className="w-5 h-5 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                    />
                  </svg>
                  <div>
                    <div className="text-white font-medium">Export Data</div>
                    <div className="text-xs text-gray-400">Download your watched history and preferences</div>
                  </div>
                </div>
                <span className="text-xs text-gray-500 bg-neutral-700 px-2 py-1 rounded">
                  Coming Soon
                </span>
              </div>

              <div className="flex items-center justify-between p-4 bg-neutral-750 rounded-xl cursor-not-allowed">
                <div className="flex items-center gap-3">
                  <svg
                    className="w-5 h-5 text-red-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                  <div>
                    <div className="text-white font-medium">Delete Account</div>
                    <div className="text-xs text-gray-400">
                      Permanently delete your account and all data
                    </div>
                  </div>
                </div>
                <span className="text-xs text-gray-500 bg-neutral-700 px-2 py-1 rounded">
                  Coming Soon
                </span>
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-neutral-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
