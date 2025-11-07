/**
 * API client for YouTube Feed Aggregator backend
 */

export interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
}

export interface Channel {
  id: number;
  channel_id: string;
  channel_title: string;
  channel_custom_url?: string | null;
  active: boolean;
  added_at: string;
}

export interface FeedItem {
  video_id: string;
  title: string;
  link: string;
  published: string;
  channel_id: string;
  channel_title: string;
  thumbnail_url?: string;
  description?: string;
  watched?: boolean;
}

export interface FeedResponse {
  items: FeedItem[];
  next_cursor: string | null;
}

export interface SubscriptionsResponse {
  channels: Channel[];
}

export interface RefreshResponse {
  count: number;
  channels: Array<{
    id: number;
    channel_id: string;
    channel_title: string;
    active: boolean;
  }>;
}

class APIClient {
  private baseURL: string;

  constructor(baseURL: string = '') {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options: {
      method?: string;
      headers?: Record<string, string>;
      body?: string;
    } = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      credentials: 'include', // Important: send cookies with requests
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(errorData.detail || `HTTP ${response.status}`);
    }

    // Handle empty responses (204 No Content, empty body, or non-JSON responses)
    if (response.status === 204 || response.headers.get('content-length') === '0') {
      return undefined as T;
    }

    if (response.headers.get('content-type')?.includes('application/json') !== true) {
      return undefined as T;
    }

    return response.json();
  }

  /**
   * Redirect to OAuth login
   */
  login() {
    window.location.href = '/auth/login';
  }

  /**
   * Logout the current user
   */
  async logout(): Promise<{ message: string }> {
    return this.request<{ message: string }>('/auth/logout', {
      method: 'POST',
    });
  }

  /**
   * Get current user information
   */
  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  /**
   * Get user's subscribed channels
   */
  async getSubscriptions(): Promise<SubscriptionsResponse> {
    return this.request<SubscriptionsResponse>('/api/subscriptions');
  }

  /**
   * Refresh subscriptions from YouTube API
   */
  async refreshSubscriptions(): Promise<RefreshResponse> {
    return this.request<RefreshResponse>('/api/subscriptions/refresh', {
      method: 'POST',
    });
  }

  /**
   * Get feed with pagination and filtering
   */
  async getFeed(params?: {
    limit?: number;
    cursor?: string | null;
    channel_id?: string | null;
  }): Promise<FeedResponse> {
    const searchParams = new URLSearchParams();

    if (params?.limit) {
      searchParams.append('limit', params.limit.toString());
    }
    if (params?.cursor) {
      searchParams.append('cursor', params.cursor);
    }
    if (params?.channel_id) {
      searchParams.append('channel_id', params.channel_id);
    }

    const queryString = searchParams.toString();
    const endpoint = `/api/feed${queryString ? `?${queryString}` : ''}`;

    return this.request<FeedResponse>(endpoint);
  }

  /**
   * Mark a video as watched
   */
  async markVideoWatched(video_id: string, channel_id: string): Promise<void> {
    await this.request<void>('/api/watched', {
      method: 'POST',
      body: JSON.stringify({ video_id, channel_id }),
    });
  }

  /**
   * Unmark a video as watched
   */
  async unmarkVideoWatched(video_id: string): Promise<void> {
    await this.request<void>(`/api/watched/${video_id}`, {
      method: 'DELETE',
    });
  }

  /**
   * Get list of watched video IDs
   */
  async getWatchedVideos(): Promise<{ video_ids: string[] }> {
    return this.request<{ video_ids: string[] }>('/api/watched');
  }
}

// Export a singleton instance
export const api = new APIClient();
