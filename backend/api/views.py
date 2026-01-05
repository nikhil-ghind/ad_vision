from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import base64

from content_analysis.analyzer import analyze_image, analyze_text
from targeting.engine import UserProfile, AdCampaign, run_auction

_CAMPAIGNS = [
    AdCampaign("c1", "TechCorp", 5.0, ["technology", "gadgets"], ["25-34", "35-44"], ["US", "CA"], 100.0),
    AdCampaign("c2", "FitLife",  3.0, ["fitness", "health"],     ["18-24", "25-34"], ["US"],        50.0),
    AdCampaign("c3", "FoodHub",  2.0, ["food", "cooking"],       ["25-34", "45-54"], ["US", "UK"],  80.0),
]


@method_decorator(csrf_exempt, name="dispatch")
class AnalyzeContentView(View):
    def post(self, request):
        body = json.loads(request.body)
        if "text" in body:
            result = analyze_text(body["text"])
        elif "image_b64" in body:
            img_bytes = base64.b64decode(body["image_b64"])
            result = analyze_image(img_bytes)
        else:
            return JsonResponse({"error": "Provide 'text' or 'image_b64'"}, status=400)
        return JsonResponse(result)


@method_decorator(csrf_exempt, name="dispatch")
class ServeAdView(View):
    def post(self, request):
        body = json.loads(request.body)
        user = UserProfile(
            user_id=body.get("user_id", "anon"),
            age_group=body.get("age_group", "25-34"),
            interests=body.get("interests", []),
            location=body.get("location", "US"),
            device=body.get("device", "desktop"),
            visit_count=int(body.get("visit_count", 0)),
        )
        result = run_auction(user, _CAMPAIGNS)
        if result.winner:
            return JsonResponse({
                "campaign_id": result.winner.campaign_id,
                "advertiser": result.winner.advertiser,
                "clearing_price_cpm": result.clearing_price,
                "score": result.score,
            })
        return JsonResponse({"ad": None, "reason": result.reason})
