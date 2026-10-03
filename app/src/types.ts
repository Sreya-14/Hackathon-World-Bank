// The listing data the tourist app reads. The backend serves this as GeoJSON;
// the full contract is in docs/LISTINGS_API.md.

export type Lang = 'en' | 'de';
export type Category = 'food' | 'craft' | 'textile' | 'tour' | 'experience' | 'other';
/** How exactly the vendor chose to show their location. */
export type Privacy = 'exact' | 'area' | 'meeting';

export interface ListingProps {
  id: number;
  category: Category;
  title: Record<Lang, string>;
  description: Record<Lang, string>;
  /** Only present if the vendor said it; never invented. */
  price: string | null;
  hours: string | null;
  photo_url: string | null;
  privacy: Privacy;
  /** For "area": the point is the centre of a square this wide. */
  radius_m: number | null;
  verified: boolean;
  met_count: number;
  days_since_checkin: number | null;
  /** Sample data, not a real vendor. */
  seed: boolean;
  updated_at: string;
  /** Only in the offline bundle (/api/bundle). Otherwise fetched on tap via /contact. */
  whatsapp_url?: string | null;
}

export interface Listing {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: ListingProps;
}

export interface ListingCollection {
  type: 'FeatureCollection';
  features: Listing[];
  generated_at?: string;
}
