import { ACTIVATION_PRECISION } from '@/lib/utils/activations';
import * as Tooltip from '@radix-ui/react-tooltip';
import { ActivationPartialWithRelations } from 'prisma/generated/zod';

export default function ActivationItemTokenTooltip({
  activation,
  token,
  tokenIndex,
  dfaMaxIndex,
}: {
  activation: ActivationPartialWithRelations;
  token: string;
  tokenIndex: number;
  dfaMaxIndex: number;
}) {
  type LogitsTokenValueType = {
    t: string[] | undefined;
    v: number[] | undefined;
  }[];

  return (
    <Tooltip.Portal>
      <Tooltip.Content
        className="z-50 flex w-full flex-col items-center gap-y-1.5 rounded border bg-white px-4 py-2 text-center text-xs font-semibold text-slate-700 shadow"
        sideOffset={3}
      >
        <div className="whitespace-pre-wrap rounded bg-slate-300 px-1 font-mono">{token.replaceAll('\n', '\\n')}</div>
        {activation.dfaValues && activation.dfaValues.length > 0 && (
          <div className="font-base flex flex-row gap-x-2 font-normal leading-none">
            <div>DFA</div>
            <div>
              {activation.dfaValues[tokenIndex] >= 0 ? '+' : ''}
              {activation.dfaValues[tokenIndex].toFixed(ACTIVATION_PRECISION)}
            </div>
          </div>
        )}
        {activation.values && (
          <div className="font-base flex flex-row gap-x-2 font-normal leading-none">
            <div>Feature Activation</div>
            <div>
              {activation.values[tokenIndex] >= 0 ? '+' : ''}
              {activation.values[tokenIndex].toFixed(ACTIVATION_PRECISION)}
            </div>
          </div>
        )}
        {activation.lossValues && activation.lossValues.length > 0 && (
          <div className="font-base flex flex-row gap-x-2 font-normal leading-none">
            <div>Loss Contribution</div>
            <div>
              {activation.lossValues[tokenIndex] >= 0 ? '+' : ''}
              {activation.lossValues[tokenIndex].toFixed(ACTIVATION_PRECISION)}
            </div>
          </div>
        )}
        {tokenIndex === activation.dfaTargetIndex && activation.dfaValues && (
          <div className="font-base mt-2 flex w-full flex-row items-center justify-center gap-x-2 border-t border-t-slate-200 pt-2 font-normal leading-none">
            <div>DFA (Target)</div>
            <div className="flex flex-col items-center justify-center gap-y-1">
              <div className="whitespace-pre-wrap rounded bg-slate-300 px-1 py-0.5 font-mono">
                {activation.tokens && activation.tokens[dfaMaxIndex]}
              </div>
              {activation.dfaValues && (
                <>
                  {activation.dfaValues[dfaMaxIndex] >= 0 ? '+' : ''}
                  {activation.dfaValues[dfaMaxIndex].toFixed(ACTIVATION_PRECISION)}
                </>
              )}
            </div>
          </div>
        )}
        <div className="mt-2 flex w-full flex-row gap-x-3 text-[11px]">
          <div className="flex basis-1/2 flex-col gap-y-0.5">
            {activation.logitContributions &&
              Object.entries(JSON.parse(activation.logitContributions)).map(([key, val], index) => {
                if (key === 'pos') {
                  const v = val as LogitsTokenValueType;
                  if (v[tokenIndex] && v[tokenIndex].t !== undefined && v[tokenIndex].t!.length > 0) {
                    return v[tokenIndex].t!.map((a, i) => (
                      <div className="flex flex-row gap-x-1" key={i}>
                        <div
                          key={`${tokenIndex}-${index}-${i}`}
                          className="flex basis-2/3 justify-end whitespace-pre-line font-mono"
                        >
                          <div className="whitespace-pre-line rounded bg-slate-200 px-1">{a}</div>
                        </div>

                        <div key={`${tokenIndex}-${index}-val-${i}`} className="basis-1/3 text-left">
                          {v[tokenIndex].v![i] >= 0 && '+'}
                          {v[tokenIndex].v![i].toFixed(3)}
                        </div>
                      </div>
                    ));
                  }
                }
                return '';
              })}
          </div>
          <div className="flex basis-1/2 flex-col gap-y-0.5">
            {activation.logitContributions &&
              Object.entries(JSON.parse(activation.logitContributions)).map(([key, val], index) => {
                if (key === 'neg') {
                  const v = val as LogitsTokenValueType;
                  if (v[tokenIndex] && v[tokenIndex].t !== undefined && v[tokenIndex].t!.length > 0) {
                    return v[tokenIndex].t!.map((a, i) => (
                      <div className="flex flex-row items-center justify-center gap-x-1" key={i}>
                        <pre key={`${tokenIndex}-${index}-${i}`} className="flex basis-2/3 justify-end font-mono">
                          <div className="whitespace-pre-line rounded bg-slate-200 px-1">{a}</div>
                        </pre>

                        <div key={`${tokenIndex}-${index}-val-${i}`} className="basis-1/3 text-left">
                          {v[tokenIndex].v![i] >= 0 && '+'}
                          {v[tokenIndex].v![i].toFixed(3)}
                        </div>
                      </div>
                    ));
                  }
                }
                return '';
              })}
          </div>
        </div>
      </Tooltip.Content>
    </Tooltip.Portal>
  );
}
