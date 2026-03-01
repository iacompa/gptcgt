import { getSignInUrl } from '@workos-inc/authkit-nextjs';
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export const GET = async (request: Request) => {
    const signInUrl = await getSignInUrl();
    return NextResponse.redirect(signInUrl);
};
