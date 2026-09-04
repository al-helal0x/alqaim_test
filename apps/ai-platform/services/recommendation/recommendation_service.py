"""IRecommendationService — القسم 7.8: توصيات إعادة الطلب (مرحلة لاحقة —
7.13 المرحلة 3). تنفيذ أولي بسيط وشفاف عمداً (Simple Reorder Point)، متّسق
مع توصية القسم 7.8 نفسها: 'الشفافية أهم من الدقة الهامشية' — يُستبدَل لاحقاً
بنماذج تنبؤ أكثر تعقيداً خلف نفس الواجهة عند الحاجة الفعلية.
"""
import math


class SimpleReorderRecommendationService:
    def suggest_reorder(
        self, *, current_qty: float, avg_daily_usage: float, lead_time_days: int
    ) -> dict:
        if avg_daily_usage <= 0:
            return {
                "should_reorder": False,
                "reason": "لا يوجد استهلاك يومي متوسط كافٍ لحساب نقطة إعادة الطلب",
            }

        # نقطة إعادة الطلب الكلاسيكية + هامش أمان بسيط (20%) — شفافة وقابلة للتفسير
        safety_margin = 1.2
        reorder_point = avg_daily_usage * lead_time_days * safety_margin
        should_reorder = current_qty <= reorder_point
        suggested_qty = math.ceil(reorder_point * 1.5 - current_qty) if should_reorder else 0

        return {
            "should_reorder": should_reorder,
            "reorder_point": round(reorder_point, 2),
            "current_qty": current_qty,
            "suggested_order_qty": max(suggested_qty, 0),
            "explanation": (
                f"بمعدل استهلاك {avg_daily_usage}/يوم ومدة توريد {lead_time_days} يوم، "
                f"نقطة إعادة الطلب المقترحة هي {round(reorder_point, 2)}"
            ),
        }
