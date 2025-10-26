import { prisma } from '@/lib/db';
// eslint-disable-next-line import/no-cycle
import CustomPrismaAdapterForNextAuth from '@/lib/db/custom-prisma-adapter';
import { sendLoginEmail, sendWelcomeEmail } from '@/lib/email/email';
import {
  APPLE_CLIENT_ID,
  APPLE_CLIENT_SECRET,
  CONTACT_EMAIL_ADDRESS,
  EMAIL_SENDING_PROVIDER,
  GITHUB_ID,
  GITHUB_SECRET,
  GOOGLE_CLIENT_ID,
  GOOGLE_CLIENT_SECRET,
  SMTP_SERVER_HOST,
  SMTP_SERVER_PORT,
} from '@/lib/env';
import { User, UserSecretType } from '@prisma/client';
import crypto from 'crypto';
import type { NextAuthOptions } from 'next-auth/index';
import AppleProvider from 'next-auth/providers/apple';
import Email from 'next-auth/providers/email';
import GithubProvider, { GithubProfile } from 'next-auth/providers/github';
import GoogleProvider from 'next-auth/providers/google';

export const authOptions: NextAuthOptions = {
  adapter: CustomPrismaAdapterForNextAuth(prisma),
  // https://github.com/nextauthjs/next-auth/discussions/6898
  cookies: {
    pkceCodeVerifier: {
      name: 'next-auth.pkce.code_verifier',
      options: {
        httpOnly: true,
        sameSite: 'none',
        path: '/',
        secure: true,
      },
    },
  },
  providers: [
    AppleProvider({
      clientId: APPLE_CLIENT_ID,
      clientSecret: APPLE_CLIENT_SECRET,
    }),
    GoogleProvider({
      clientId: GOOGLE_CLIENT_ID,
      clientSecret: GOOGLE_CLIENT_SECRET,
      authorization: {
        params: {
          prompt: 'consent',
          access_type: 'offline',
          response_type: 'code',
        },
      },
    }),
    GithubProvider({
      clientId: GITHUB_ID,
      clientSecret: GITHUB_SECRET,
      profile(profile: GithubProfile) {
        return {
          id: profile.id.toString(),
          name: `${profile.login}-${Math.floor(Math.random() * 1000)}`,
          githubUsername: profile.login,
          email: profile.email,
          image: profile.avatar_url,
        };
      },
    }),
    // https://github.com/nextauthjs/next-auth/issues/4965
    Email(
      EMAIL_SENDING_PROVIDER === 'smtp'
        ? {
            // Use NextAuth's built-in SMTP handling
            server: {
              host: SMTP_SERVER_HOST,
              port: Number(SMTP_SERVER_PORT),
              secure: false,
              requireTLS: true,
            },
            from: CONTACT_EMAIL_ADDRESS,
          }
        : {
            // Use custom handling for AWS/Resend
            generateVerificationToken() {
              const random = crypto.getRandomValues(new Uint8Array(8));
              return Buffer.from(random).toString('hex').slice(0, 6);
            },
            async sendVerificationRequest(params) {
              // eslint-disable-next-line @typescript-eslint/no-unused-vars
              const { identifier } = params;

              const url = new URL(params.url);
              // url.searchParams.delete("token") // uncomment if you want the user to type this manually
              const signInURL = new URL(`/auth/email?${url.searchParams}`, url.origin);

              await sendLoginEmail(identifier, signInURL.toString());
            },
          },
    ),
  ],
  events: {
    async createUser(message) {
      const user = message.user as User;
      // create a secret for the user
      const secretValue = `sk-np-${crypto
        .randomBytes(32)
        .toString('base64')
        .replace(/\+/g, '0')
        .replace(/\//g, '0')
        // eslint-disable-next-line no-useless-escape
        .replace(/\=/g, '0')}`;
      await prisma.userSecret.create({
        data: {
          user: {
            connect: {
              name: user.name,
            },
          },
          type: UserSecretType.NEURONPEDIA,
          value: secretValue,
        },
      });
      if (user && user.email && user.emailUnsubscribeCode) {
        console.log('new created user');
        await sendWelcomeEmail(user.email, user.emailUnsubscribeCode);
      } else {
        throw new Error('invalid user created');
      }
    },
  },
  callbacks: {
    session: async ({ session, user }) => {
      if (session?.user) {
        // eslint-disable-next-line no-param-reassign
        session.user.id = user.id;
        // eslint-disable-next-line no-param-reassign
        session.user.name = user.name || '';
      }
      return session;
    },
  },
};
