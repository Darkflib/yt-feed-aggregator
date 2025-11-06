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
}

// Export a singleton instance
export const api = new APIClient();
