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
  duration?: string | null;
  includes?: Record<Lang, string[]>;
  /** Places the host named ("Meppadi"). The pin's precision is in `privacy`. */
  place?: string | null;
  /** The vendor's own description of where to meet, if she gave one. */
  meeting_point?: Record<Lang, string | null>;
  /** Languages produced by machine translation (labelled in the UI). */
  machine_translated?: Lang[];
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
